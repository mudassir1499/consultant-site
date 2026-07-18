"""Tests for the custom admin portal: access control + management CRUD."""
from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from users.models import User
from office.models import Office
from finance.models import bank_account
from pages.models import SiteSettings
from scholarships.models import Application, scholarships


class AdminPortalAccessTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="a", password="pw")
        self.agent = User.objects.create_user(username="ag", password="pw", role="agent")

    def test_non_superuser_is_redirected(self):
        self.client.force_login(self.agent)
        r = self.client.get("/admin-portal/")
        self.assertEqual(r.status_code, 302)  # bounced to admin login

    def test_superuser_can_open_dashboard(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/admin-portal/").status_code, 200)


class AdminPortalManagementTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="a", password="pw")
        self.client.force_login(self.admin)
        self.office = Office.objects.create(name="HQ Office", code="hq", is_default=True)

    def test_create_agent_user(self):
        self.client.post("/admin-portal/users/create/?role=agent", {
            "username": "new_agent", "password": "password123", "email": "n@a.com",
            "role": "agent", "status": "active", "office": str(self.office.id),
        })
        u = User.objects.get(username="new_agent")
        self.assertEqual(u.role, "agent")
        self.assertTrue(u.check_password("password123"))
        self.assertEqual(u.office, self.office)

    def test_toggle_and_reset_password(self):
        u = User.objects.create_user(username="s", password="old12345", role="user", status="active")
        self.client.post(f"/admin-portal/users/{u.id}/toggle-status/")
        u.refresh_from_db()
        self.assertEqual(u.status, "suspended")
        self.assertFalse(u.is_active)

        self.client.post(f"/admin-portal/users/{u.id}/reset-password/", {"new_password": "brandnew123"})
        u.refresh_from_db()
        self.assertTrue(u.check_password("brandnew123"))

    def test_create_office_and_bank(self):
        self.client.post("/admin-portal/offices/create/", {
            "name": "Cairo", "code": "cairo", "is_active": "on",
        })
        self.assertTrue(Office.objects.filter(code="cairo").exists())

        self.client.post("/admin-portal/banks/create/", {
            "bank_name": "Test Bank", "account_number": "123", "swift_code": "X", "status": "active",
        })
        self.assertTrue(bank_account.objects.filter(bank_name="Test Bank").exists())

    def test_edit_site_settings(self):
        self.client.post("/admin-portal/settings/", {
            "site_name": "New Name", "contact_email": "info@x.com",
        })
        self.assertEqual(SiteSettings.load().site_name, "New Name")

    def test_reassign_agent_and_hq(self):
        student = User.objects.create_user(username="stu", password="pw", role="user")
        agent = User.objects.create_user(username="ag2", password="pw", role="agent")
        hq = User.objects.create_user(username="hq2", password="pw", role="headquarters", status="active")
        sch = scholarships.objects.create(
            name="S", description="d", city="C", major="M", degree="master", language="EN",
            scholarship_type="full", deadline=timezone.now().date() + timedelta(days=30),
            semester="fall", price=Decimal("10"), eligibility="e",
        )
        app = Application.objects.create(user=student, scholarship=sch, office=self.office)

        self.client.post(f"/admin-portal/applications/{app.app_id}/assign-agent/", {"agent_id": agent.id})
        self.client.post(f"/admin-portal/applications/{app.app_id}/reassign-hq/", {"hq_id": hq.id})
        app.refresh_from_db()
        self.assertEqual(app.assigned_agent, agent)
        self.assertEqual(app.assigned_hq, hq)


class AgentScholarshipTest(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(username="ag", password="pw", role="agent", status="active")

    def test_agent_creates_scholarship_with_zero_commission(self):
        self.client.force_login(self.agent)
        self.client.post("/agent/scholarships/create/", {
            "name": "Agent Sch", "description": "d", "city": "C", "major": "M", "degree": "master",
            "language": "EN", "scholarship_type": "full", "deadline": "2027-01-01",
            "semester": "fall", "price": "500", "eligibility": "e",
        })
        s = scholarships.objects.get(name="Agent Sch")
        # Commissions stay admin-controlled → default 0 regardless of any posted value.
        self.assertEqual(s.agent_commission, Decimal("0"))
        self.assertEqual(s.hq_commission, Decimal("0"))

    def test_non_agent_cannot_create_scholarship(self):
        student = User.objects.create_user(username="stu", password="pw", role="user")
        self.client.force_login(student)
        r = self.client.get("/agent/scholarships/create/")
        self.assertEqual(r.status_code, 403)
