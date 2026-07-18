"""
End-to-end workflow test: drives one application through every stage via the
real view endpoints (office → agent → HQ → admin) and asserts both the status
transitions and the wallet commission math at each step.
"""
import shutil
import tempfile
from decimal import Decimal
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from users.models import User
from office.models import Office
from scholarships.models import Application, scholarships
from finance.models import application_payment
from finance.services import get_or_create_wallet

MEDIA = tempfile.mkdtemp()


def pdf(name):
    return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")


@override_settings(MEDIA_ROOT=MEDIA)
class FullWorkflowTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.office = Office.objects.create(name="Test Office", code="test", is_default=True)
        self.staff = User.objects.create_user(
            username="w_office", password="pw", role="office", office=self.office, status="active"
        )
        self.agent = User.objects.create_user(
            username="w_agent", password="pw", role="agent", office=self.office, status="active"
        )
        self.hq = User.objects.create_user(
            username="w_hq", password="pw", role="headquarters", status="active"
        )
        self.admin = User.objects.create_superuser(username="w_admin", password="pw")
        self.student = User.objects.create_user(
            username="w_student", password="pw", role="user", office=self.office, status="active"
        )
        self.sch = scholarships.objects.create(
            name="Test Scholarship", description="d", city="C", major="M", degree="master",
            language="English", scholarship_type="full",
            deadline=timezone.now().date() + timedelta(days=90),
            semester="fall", price=Decimal("1000"), eligibility="e",
            agent_commission=Decimal("200"), hq_commission=Decimal("100"),
        )

    def test_full_lifecycle_and_wallet(self):
        # ── Office creates + prepares the application ──────────────────
        self.client.force_login(self.staff)
        self.client.post("/office/applications/create/", {
            "scholarship_id": self.sch.id, "student_mode": "existing", "student_id": self.student.id,
        })
        app = Application.objects.get(user=self.student, scholarship=self.sch)
        self.assertEqual(app.status, "draft")

        self.client.post(f"/office/applications/{app.app_id}/upload-documents/", {
            "passport": pdf("p.pdf"), "photo": pdf("ph.pdf"),
        })
        self.client.post(f"/office/applications/{app.app_id}/submit/")
        self.client.post(f"/office/applications/{app.app_id}/start-review/")
        self.client.post(f"/office/applications/{app.app_id}/verify-documents/")
        app.refresh_from_db()
        self.assertEqual(app.status, "documents_verified")

        self.client.post(f"/office/applications/{app.app_id}/make-payment/", {
            "amount": "1000", "receipt_pdf": pdf("r.pdf"), "transaction_id": "TXN1",
        })
        self.client.post(f"/office/applications/{app.app_id}/verify-payment/")
        app.refresh_from_db()
        self.assertEqual(app.status, "payment_verified")
        self.assertTrue(application_payment.objects.filter(application=app).exists())

        self.client.post(f"/office/applications/{app.app_id}/forward-to-agent/", {"agent_id": self.agent.id})
        app.refresh_from_db()
        self.assertEqual(app.assigned_agent, self.agent)

        # ── Agent approves → HQ auto-assigned ─────────────────────────
        self.client.force_login(self.agent)
        self.client.post(f"/agent/applications/{app.app_id}/approve/", {"deadline_days": "10"})
        app.refresh_from_db()
        self.assertEqual(app.status, "approved")
        self.assertEqual(app.assigned_hq, self.hq)

        # ── HQ applies + uploads admission letter ─────────────────────
        self.client.force_login(self.hq)
        self.client.post(f"/hq/applications/{app.app_id}/mark-applied/")
        app.refresh_from_db()
        self.assertEqual(app.status, "in_progress")
        self.client.post(f"/hq/applications/{app.app_id}/upload-letter/", {"admission_letter": pdf("l.pdf")})
        app.refresh_from_db()
        self.assertEqual(app.status, "admission_letter_uploaded")

        # ── Agent approves letter → commissions parked in UPCOMING ────
        self.client.force_login(self.agent)
        self.client.post(f"/agent/admission-letter/{app.app_id}/approve/")
        app.refresh_from_db()
        self.assertEqual(app.status, "admission_letter_approved")
        agent_w = get_or_create_wallet(self.agent)
        hq_w = get_or_create_wallet(self.hq)
        self.assertEqual(agent_w.upcoming_payments, Decimal("200"))
        self.assertEqual(hq_w.upcoming_payments, Decimal("100"))
        self.assertEqual(agent_w.current_balance, Decimal("0"))

        # ── HQ uploads JW02, agent approves → moves to BALANCE ────────
        self.client.force_login(self.hq)
        self.client.post(f"/hq/jw02/{app.app_id}/", {"jw02_form": pdf("j.pdf")})
        app.refresh_from_db()
        self.assertEqual(app.status, "jw02_uploaded")

        self.client.force_login(self.agent)
        self.client.post(f"/agent/jw02/{app.app_id}/approve/")
        app.refresh_from_db()
        self.assertEqual(app.status, "complete")
        agent_w.refresh_from_db()
        hq_w.refresh_from_db()
        self.assertEqual(agent_w.upcoming_payments, Decimal("0"))
        self.assertEqual(agent_w.current_balance, Decimal("200"))
        self.assertEqual(agent_w.total_earned, Decimal("200"))
        self.assertEqual(hq_w.current_balance, Decimal("100"))

        # ── Withdrawal: agent requests, admin approves ────────────────
        self.client.force_login(self.agent)
        self.client.post("/agent/wallet/withdraw/", {"amount": "150"})
        agent_w.refresh_from_db()
        self.assertEqual(agent_w.current_balance, Decimal("50"))
        self.assertEqual(agent_w.pending_withdrawals, Decimal("150"))
        wd = agent_w.withdrawal_requests.get()
        self.assertEqual(wd.status, "pending")

        self.client.force_login(self.admin)
        self.client.post(f"/admin-portal/withdrawals/{wd.id}/approve/")
        agent_w.refresh_from_db()
        wd.refresh_from_db()
        self.assertEqual(wd.status, "approved")
        self.assertEqual(agent_w.pending_withdrawals, Decimal("0"))
        self.assertEqual(agent_w.total_withdrawn, Decimal("150"))
        self.assertEqual(agent_w.current_balance, Decimal("50"))
