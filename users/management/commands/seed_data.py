"""
Management command to populate the database with realistic sample data.
Usage:  python manage.py seed_data
        python manage.py seed_data --flush   (clear all data first)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random

from users.models import User, Notification
from scholarships.models import (
    scholarships, Application, AdmissionLetter, JW02Form, ApplicationStatusHistory,
)
from finance.models import (
    bank_account, application_payment, Wallet, WalletTransaction, WithdrawalRequest,
)


class Command(BaseCommand):
    help = "Seed the database with sample data for the entire system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing data before seeding",
        )

    # ------------------------------------------------------------------ #
    #  helpers
    # ------------------------------------------------------------------ #
    def _now(self):
        return timezone.now()

    def _past(self, days=0, hours=0):
        return self._now() - timedelta(days=days, hours=hours)

    # ------------------------------------------------------------------ #
    #  main
    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing existing data …")
            ApplicationStatusHistory.objects.all().delete()
            JW02Form.objects.all().delete()
            AdmissionLetter.objects.all().delete()
            application_payment.objects.all().delete()
            Application.objects.all().delete()
            WalletTransaction.objects.all().delete()
            WithdrawalRequest.objects.all().delete()
            Wallet.objects.all().delete()
            Notification.objects.all().delete()
            bank_account.objects.all().delete()
            scholarships.objects.all().delete()
            User.objects.exclude(is_superuser=True).delete()

        self._create_users()
        self._create_bank_accounts()
        self._create_scholarships()
        self._create_wallets()
        self._create_applications()
        self._create_payments()
        self._create_wallet_transactions()
        self._create_notifications()

        self.stdout.write(self.style.SUCCESS("\n✅  Sample data seeded successfully!"))
        self._print_summary()

    # ------------------------------------------------------------------ #
    #  1. Users
    # ------------------------------------------------------------------ #
    def _create_users(self):
        self.stdout.write("Creating users …")

        # Admin / superuser (skip if exists)
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@educonsult.com",
                "first_name": "System",
                "last_name": "Admin",
                "role": "user",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password("admin123")
            admin.save()

        # Office workers
        self.office1 = self._get_or_create_user(
            "sarah_office", "sarah@educonsult.com", "Sarah", "Williams",
            "office", "office123"
        )
        self.office2 = self._get_or_create_user(
            "mike_office", "mike@educonsult.com", "Mike", "Johnson",
            "office", "office123"
        )

        # Main agents
        self.agent1 = self._get_or_create_user(
            "li_agent", "li.wei@educonsult.com", "Li", "Wei",
            "agent", "agent123", phone="+86-138-0000-1111"
        )
        self.agent2 = self._get_or_create_user(
            "ahmed_agent", "ahmed@educonsult.com", "Ahmed", "Hassan",
            "agent", "agent123", phone="+20-100-000-2222"
        )

        # Headquarters
        self.hq1 = self._get_or_create_user(
            "chen_hq", "chen@educonsult.com", "Chen", "Ming",
            "headquarters", "hq123", phone="+86-139-0000-3333"
        )
        self.hq2 = self._get_or_create_user(
            "wang_hq", "wang@educonsult.com", "Wang", "Fei",
            "headquarters", "hq123", phone="+86-139-0000-4444"
        )

        # Regular student users
        self.student1 = self._get_or_create_user(
            "john_doe", "john.doe@student.com", "John", "Doe",
            "user", "student123", phone="+1-555-0001"
        )
        self.student2 = self._get_or_create_user(
            "maria_garcia", "maria@student.com", "Maria", "Garcia",
            "user", "student123", phone="+34-600-0002"
        )
        self.student3 = self._get_or_create_user(
            "fatima_ali", "fatima@student.com", "Fatima", "Ali",
            "user", "student123", phone="+966-50-0003"
        )
        self.student4 = self._get_or_create_user(
            "omar_khan", "omar@student.com", "Omar", "Khan",
            "user", "student123", phone="+92-300-0004"
        )
        self.student5 = self._get_or_create_user(
            "yuki_tanaka", "yuki@student.com", "Yuki", "Tanaka",
            "user", "student123", phone="+81-90-0005"
        )
        self.student6 = self._get_or_create_user(
            "david_kim", "david@student.com", "David", "Kim",
            "user", "student123", phone="+82-10-0006"
        )

    def _get_or_create_user(self, username, email, first, last, role, password, phone=""):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first,
                "last_name": last,
                "role": role,
                "phone": phone,
                "status": "active",
            },
        )
        if created:
            user.set_password(password)
            user.save()
        return user

    # ------------------------------------------------------------------ #
    #  2. Bank accounts
    # ------------------------------------------------------------------ #
    def _create_bank_accounts(self):
        self.stdout.write("Creating bank accounts …")
        accounts = [
            ("Bank of China", "6222021234567890", "EduConsult International", "CN12BKCH12345678901234", "BKCHCNBJ"),
            ("ICBC", "6212261234567891", "EduConsult Ltd", "CN34ICBK23456789012345", "ICBKCNBJ"),
            ("China Construction Bank", "6227001234567892", "EduConsult Services", None, "PCBCCNBJ"),
        ]
        for name, num, holder, iban, swift in accounts:
            bank_account.objects.get_or_create(
                account_number=num,
                defaults={
                    "bank_name": name,
                    "account_holder_name": holder,
                    "iban": iban,
                    "swift_code": swift,
                    "status": "active",
                },
            )

    # ------------------------------------------------------------------ #
    #  3. Scholarships
    # ------------------------------------------------------------------ #
    def _create_scholarships(self):
        self.stdout.write("Creating scholarships …")
        data = [
            {
                "name": "Chinese Government Scholarship - Full Ride",
                "description": "The Chinese Government Scholarship (CGS) is a prestigious program covering tuition, accommodation, living expenses, and medical insurance for international students.",
                "city": "Beijing",
                "major": "Computer Science",
                "degree": "master",
                "language": "English",
                "scholarship_type": "full",
                "deadline": self._now().date() + timedelta(days=90),
                "semester": "fall",
                "price": Decimal("500.00"),
                "eligibility": "Bachelor's degree with GPA ≥ 3.0. Age under 35. Non-Chinese citizen.",
                "note": "HSK 4 required for Chinese-taught programs.",
                "agent_commission": Decimal("200.00"),
                "hq_commission": Decimal("150.00"),
            },
            {
                "name": "Shanghai Municipal Scholarship",
                "description": "Full tuition waiver and monthly stipend for students enrolling in top Shanghai universities including Fudan and SJTU.",
                "city": "Shanghai",
                "major": "Business Administration",
                "degree": "bachelor",
                "language": "English",
                "scholarship_type": "full",
                "deadline": self._now().date() + timedelta(days=60),
                "semester": "fall",
                "price": Decimal("350.00"),
                "eligibility": "High school diploma with excellent grades. IELTS 6.0 or equivalent.",
                "note": "",
                "agent_commission": Decimal("150.00"),
                "hq_commission": Decimal("100.00"),
            },
            {
                "name": "Zhejiang University Merit Scholarship",
                "description": "Merit-based scholarship covering tuition and providing a living allowance for outstanding PhD candidates at Zhejiang University.",
                "city": "Hangzhou",
                "major": "Mechanical Engineering",
                "degree": "phd",
                "language": "English",
                "scholarship_type": "merit",
                "deadline": self._now().date() + timedelta(days=120),
                "semester": "spring",
                "price": Decimal("600.00"),
                "eligibility": "Master's degree. Published research in relevant field. Age under 40.",
                "note": "Research proposal required.",
                "agent_commission": Decimal("250.00"),
                "hq_commission": Decimal("200.00"),
            },
            {
                "name": "Guangdong Provincial Scholarship",
                "description": "Partial scholarship covering 50% of tuition for students at universities in Guangdong province including SYSU and SCUT.",
                "city": "Guangzhou",
                "major": "International Trade",
                "degree": "bachelor",
                "language": "Chinese",
                "scholarship_type": "partial",
                "deadline": self._now().date() + timedelta(days=45),
                "semester": "fall",
                "price": Decimal("300.00"),
                "eligibility": "High school diploma. HSK 4 required. Age 18-25.",
                "note": "Chinese language proficiency mandatory.",
                "agent_commission": Decimal("120.00"),
                "hq_commission": Decimal("80.00"),
            },
            {
                "name": "Tsinghua University Presidential Scholarship",
                "description": "Top-tier scholarship for exceptional students pursuing a Master's in Data Science at Tsinghua University, covering full tuition plus generous stipend.",
                "city": "Beijing",
                "major": "Data Science",
                "degree": "master",
                "language": "English",
                "scholarship_type": "full",
                "deadline": self._now().date() + timedelta(days=75),
                "semester": "spring",
                "price": Decimal("800.00"),
                "eligibility": "Bachelor's degree in CS, Math, or related field. GPA ≥ 3.5. GRE recommended.",
                "note": "Only 10 positions available.",
                "agent_commission": Decimal("300.00"),
                "hq_commission": Decimal("250.00"),
            },
            {
                "name": "Wuhan University Cultural Exchange Scholarship",
                "description": "Scholarship for students interested in Chinese culture and language studies at Wuhan University, including accommodation and stipend.",
                "city": "Wuhan",
                "major": "Chinese Language & Culture",
                "degree": "bachelor",
                "language": "Chinese",
                "scholarship_type": "full",
                "deadline": self._now().date() + timedelta(days=30),
                "semester": "summer",
                "price": Decimal("250.00"),
                "eligibility": "High school diploma. Interest in Chinese culture. Age 18-30.",
                "note": "Includes summer intensive program.",
                "agent_commission": Decimal("100.00"),
                "hq_commission": Decimal("75.00"),
            },
        ]

        self.scholarships_list = []
        for d in data:
            obj, _ = scholarships.objects.get_or_create(
                name=d["name"], defaults=d
            )
            self.scholarships_list.append(obj)

    # ------------------------------------------------------------------ #
    #  4. Wallets
    # ------------------------------------------------------------------ #
    def _create_wallets(self):
        self.stdout.write("Creating wallets …")
        for u in [self.agent1, self.agent2, self.hq1, self.hq2]:
            Wallet.objects.get_or_create(user=u, defaults={
                "current_balance": Decimal("0.00"),
                "upcoming_payments": Decimal("0.00"),
                "pending_withdrawals": Decimal("0.00"),
                "total_earned": Decimal("0.00"),
                "total_withdrawn": Decimal("0.00"),
            })

    # ------------------------------------------------------------------ #
    #  5. Applications (various statuses to showcase the whole workflow)
    # ------------------------------------------------------------------ #
    def _create_applications(self):
        self.stdout.write("Creating applications …")

        s = self.scholarships_list  # shorter alias

        # ---- App 1: John → CGS, COMPLETE (full lifecycle) ----
        self.app1 = self._create_app(
            self.student1, s[0], "complete",
            agent=self.agent1, hq=self.hq1,
            days_ago=60,
        )
        self._add_history(self.app1, [
            ("draft", "submitted", self.student1, 60, "Application submitted"),
            ("submitted", "under_review", self.office1, 58, "Assigned for review"),
            ("under_review", "documents_verified", self.office1, 55, "All documents verified"),
            ("documents_verified", "payment_verified", self.office1, 53, "Payment confirmed"),
            ("payment_verified", "approved", self.office1, 52, "Application approved"),
            ("approved", "in_progress", self.agent1, 50, "Agent started processing"),
            ("in_progress", "admission_letter_uploaded", self.hq1, 40, "Admission letter received from university"),
            ("admission_letter_uploaded", "admission_letter_approved", self.agent1, 38, "Letter verified and approved"),
            ("admission_letter_approved", "jw02_uploaded", self.hq1, 30, "JW02 form received"),
            ("jw02_uploaded", "jw02_approved", self.agent1, 28, "JW02 verified"),
            ("jw02_approved", "complete", self.agent1, 27, "Application complete — all documents delivered"),
        ])
        self.app1.approved_date = self._past(days=52)
        self.app1.completed_date = self._past(days=27)
        self.app1.save()

        # ---- App 2: Maria → Shanghai, APPROVED (awaiting agent pickup) ----
        self.app2 = self._create_app(
            self.student2, s[1], "approved",
            agent=self.agent1, hq=self.hq1,
            days_ago=30,
        )
        self._add_history(self.app2, [
            ("draft", "submitted", self.student2, 30, "Application submitted"),
            ("submitted", "under_review", self.office1, 28, None),
            ("under_review", "documents_verified", self.office1, 26, "Documents OK"),
            ("documents_verified", "payment_verified", self.office1, 24, "Payment receipt verified"),
            ("payment_verified", "approved", self.office2, 22, "Approved by office"),
        ])
        self.app2.approved_date = self._past(days=22)
        self.app2.save()

        # ---- App 3: Fatima → ZJU PhD, IN_PROGRESS (agent working) ----
        self.app3 = self._create_app(
            self.student3, s[2], "in_progress",
            agent=self.agent2, hq=self.hq2,
            days_ago=45,
        )
        self._add_history(self.app3, [
            ("draft", "submitted", self.student3, 45, "Submitted with all documents"),
            ("submitted", "under_review", self.office1, 43, None),
            ("under_review", "documents_verified", self.office2, 40, "All research papers verified"),
            ("documents_verified", "payment_verified", self.office2, 38, None),
            ("payment_verified", "approved", self.office1, 36, "Strong candidate — approved"),
            ("approved", "in_progress", self.agent2, 34, "Agent processing university enrollment"),
        ])
        self.app3.approved_date = self._past(days=36)
        self.app3.save()

        # ---- App 4: Omar → Guangdong, SUBMITTED (new, awaiting review) ----
        self.app4 = self._create_app(
            self.student4, s[3], "submitted",
            days_ago=5,
        )
        self._add_history(self.app4, [
            ("draft", "submitted", self.student4, 5, "Submitted application"),
        ])

        # ---- App 5: Yuki → Tsinghua, UNDER_REVIEW ----
        self.app5 = self._create_app(
            self.student5, s[4], "under_review",
            days_ago=10,
        )
        self._add_history(self.app5, [
            ("draft", "submitted", self.student5, 10, "Submitted"),
            ("submitted", "under_review", self.office1, 8, "Review started"),
        ])

        # ---- App 6: David → Wuhan, REJECTED ----
        self.app6 = self._create_app(
            self.student6, s[5], "rejected",
            days_ago=20,
        )
        self.app6.rejection_reason = "Incomplete criminal record document. Please re-apply with a valid police clearance certificate."
        self.app6.save()
        self._add_history(self.app6, [
            ("draft", "submitted", self.student6, 20, "Submitted"),
            ("submitted", "under_review", self.office2, 18, None),
            ("under_review", "rejected", self.office2, 16, "Missing criminal record certificate"),
        ])

        # ---- App 7: John → Tsinghua (2nd app), DRAFT ----
        self.app7 = self._create_app(
            self.student1, s[4], "draft",
            days_ago=2,
        )

        # ---- App 8: Maria → ZJU PhD, DOCUMENTS_VERIFIED ----
        self.app8 = self._create_app(
            self.student2, s[2], "documents_verified",
            days_ago=15,
        )
        self._add_history(self.app8, [
            ("draft", "submitted", self.student2, 15, "Submitted"),
            ("submitted", "under_review", self.office1, 13, None),
            ("under_review", "documents_verified", self.office1, 11, "All documents verified"),
        ])

        # ---- App 9: Fatima → CGS (2nd app), ADMISSION_LETTER_UPLOADED ----
        self.app9 = self._create_app(
            self.student3, s[0], "admission_letter_uploaded",
            agent=self.agent1, hq=self.hq1,
            days_ago=50,
        )
        self._add_history(self.app9, [
            ("draft", "submitted", self.student3, 50, None),
            ("submitted", "under_review", self.office1, 48, None),
            ("under_review", "documents_verified", self.office1, 46, None),
            ("documents_verified", "payment_verified", self.office1, 44, None),
            ("payment_verified", "approved", self.office1, 42, "Approved"),
            ("approved", "in_progress", self.agent1, 40, "Agent started"),
            ("in_progress", "admission_letter_uploaded", self.hq1, 15, "Letter uploaded for verification"),
        ])
        self.app9.approved_date = self._past(days=42)
        self.app9.save()

        # ---- App 10: Omar → Shanghai, PAYMENT_VERIFIED ----
        self.app10 = self._create_app(
            self.student4, s[1], "payment_verified",
            days_ago=12,
        )
        self._add_history(self.app10, [
            ("draft", "submitted", self.student4, 12, None),
            ("submitted", "under_review", self.office2, 10, None),
            ("under_review", "documents_verified", self.office2, 8, None),
            ("documents_verified", "payment_verified", self.office2, 6, "Payment confirmed"),
        ])

        # ---- App 11: Yuki → Guangdong, JW02_UPLOADED ----
        self.app11 = self._create_app(
            self.student5, s[3], "jw02_uploaded",
            agent=self.agent2, hq=self.hq2,
            days_ago=55,
        )
        self._add_history(self.app11, [
            ("draft", "submitted", self.student5, 55, None),
            ("submitted", "under_review", self.office1, 53, None),
            ("under_review", "documents_verified", self.office1, 50, None),
            ("documents_verified", "payment_verified", self.office1, 48, None),
            ("payment_verified", "approved", self.office1, 46, None),
            ("approved", "in_progress", self.agent2, 44, None),
            ("in_progress", "admission_letter_uploaded", self.hq2, 30, None),
            ("admission_letter_uploaded", "admission_letter_approved", self.agent2, 28, None),
            ("admission_letter_approved", "jw02_uploaded", self.hq2, 10, "JW02 form uploaded"),
        ])
        self.app11.approved_date = self._past(days=46)
        self.app11.save()

        # ---- App 12: David → CGS, LETTER_PENDING (revision requested) ----
        self.app12 = self._create_app(
            self.student6, s[0], "letter_pending",
            agent=self.agent1, hq=self.hq2,
            days_ago=40,
        )
        self._add_history(self.app12, [
            ("draft", "submitted", self.student6, 40, None),
            ("submitted", "under_review", self.office1, 38, None),
            ("under_review", "documents_verified", self.office1, 36, None),
            ("documents_verified", "payment_verified", self.office1, 34, None),
            ("payment_verified", "approved", self.office1, 32, None),
            ("approved", "in_progress", self.agent1, 30, None),
            ("in_progress", "admission_letter_uploaded", self.hq2, 18, None),
            ("admission_letter_uploaded", "letter_pending", self.agent1, 16, "University name misspelled on letter — please revise"),
        ])
        self.app12.approved_date = self._past(days=32)
        self.app12.save()

    def _create_app(self, user, scholarship, status, agent=None, hq=None, days_ago=0):
        app = Application.objects.create(
            scholarship=scholarship,
            user=user,
            status=status,
            assigned_agent=agent,
            assigned_hq=hq,
        )
        # Back-date applied_date
        Application.objects.filter(pk=app.pk).update(applied_date=self._past(days=days_ago))
        app.refresh_from_db()
        return app

    def _add_history(self, app, entries):
        """entries = list of (old, new, user, days_ago, note)"""
        for old, new, user, days_ago, note in entries:
            h = ApplicationStatusHistory.objects.create(
                application=app,
                old_status=old,
                new_status=new,
                changed_by=user,
                note=note,
            )
            ApplicationStatusHistory.objects.filter(pk=h.pk).update(
                changed_at=self._past(days=days_ago)
            )

    # ------------------------------------------------------------------ #
    #  6. Payments
    # ------------------------------------------------------------------ #
    def _create_payments(self):
        self.stdout.write("Creating payments …")

        # Completed payment for completed app
        application_payment.objects.get_or_create(
            application=self.app1,
            defaults={
                "amount": self.app1.scholarship.price,
                "receipt_pdf": "payments/receipts/john_doe-receipt.pdf",
                "payment_status": "completed",
                "transaction_id": "TXN-2025-000101",
            },
        )

        # Completed payment for approved app
        application_payment.objects.get_or_create(
            application=self.app2,
            defaults={
                "amount": self.app2.scholarship.price,
                "receipt_pdf": "payments/receipts/maria_garcia-receipt.pdf",
                "payment_status": "completed",
                "transaction_id": "TXN-2025-000102",
            },
        )

        # Completed payment for in-progress app
        application_payment.objects.get_or_create(
            application=self.app3,
            defaults={
                "amount": self.app3.scholarship.price,
                "receipt_pdf": "payments/receipts/fatima_ali-receipt.pdf",
                "payment_status": "completed",
                "transaction_id": "TXN-2025-000103",
            },
        )

        # Pending payment for payment_verified app (Omar → Shanghai)
        application_payment.objects.get_or_create(
            application=self.app10,
            defaults={
                "amount": self.app10.scholarship.price,
                "receipt_pdf": "payments/receipts/omar_khan-receipt.pdf",
                "payment_status": "completed",
                "transaction_id": "TXN-2025-000110",
            },
        )

        # Payment for admission_letter_uploaded app
        application_payment.objects.get_or_create(
            application=self.app9,
            defaults={
                "amount": self.app9.scholarship.price,
                "receipt_pdf": "payments/receipts/fatima_ali-2-receipt.pdf",
                "payment_status": "completed",
                "transaction_id": "TXN-2025-000109",
            },
        )

        # Payment for jw02_uploaded app
        application_payment.objects.get_or_create(
            application=self.app11,
            defaults={
                "amount": self.app11.scholarship.price,
                "receipt_pdf": "payments/receipts/yuki_tanaka-receipt.pdf",
                "payment_status": "completed",
                "transaction_id": "TXN-2025-000111",
            },
        )

        # Payment for letter_pending app
        application_payment.objects.get_or_create(
            application=self.app12,
            defaults={
                "amount": self.app12.scholarship.price,
                "receipt_pdf": "payments/receipts/david_kim-2-receipt.pdf",
                "payment_status": "completed",
                "transaction_id": "TXN-2025-000112",
            },
        )

        # Under-review payment for documents_verified app
        application_payment.objects.get_or_create(
            application=self.app8,
            defaults={
                "amount": self.app8.scholarship.price,
                "receipt_pdf": "payments/receipts/maria_garcia-2-receipt.pdf",
                "payment_status": "under_review",
                "transaction_id": "TXN-2025-000108",
            },
        )

    # ------------------------------------------------------------------ #
    #  7. Wallet transactions  (commissions for completed app)
    # ------------------------------------------------------------------ #
    def _create_wallet_transactions(self):
        self.stdout.write("Creating wallet transactions …")

        # Agent1 earned commission on completed app1
        agent_wallet = Wallet.objects.get(user=self.agent1)
        commission_agent = self.app1.scholarship.agent_commission  # $200

        WalletTransaction.objects.get_or_create(
            wallet=agent_wallet,
            application=self.app1,
            type="earning",
            defaults={
                "amount": commission_agent,
                "description": f"Commission for {self.app1.scholarship.name} (#{self.app1.app_id})",
                "status": "completed",
            },
        )
        agent_wallet.current_balance = commission_agent
        agent_wallet.total_earned = commission_agent
        agent_wallet.save()

        # HQ1 earned commission on completed app1
        hq_wallet = Wallet.objects.get(user=self.hq1)
        commission_hq = self.app1.scholarship.hq_commission  # $150

        WalletTransaction.objects.get_or_create(
            wallet=hq_wallet,
            application=self.app1,
            type="earning",
            defaults={
                "amount": commission_hq,
                "description": f"Commission for {self.app1.scholarship.name} (#{self.app1.app_id})",
                "status": "completed",
            },
        )
        hq_wallet.current_balance = commission_hq
        hq_wallet.total_earned = commission_hq
        hq_wallet.save()

        # Agent1 has upcoming for in-progress app9
        agent_wallet.upcoming_payments = self.app9.scholarship.agent_commission
        agent_wallet.save()

        # Add a pending withdrawal for agent1
        wr, created = WithdrawalRequest.objects.get_or_create(
            wallet=agent_wallet,
            status="pending",
            defaults={
                "amount": Decimal("100.00"),
            },
        )
        if created:
            agent_wallet.pending_withdrawals = Decimal("100.00")
            agent_wallet.save()

        # Agent2 has upcoming for in-progress apps
        agent2_wallet = Wallet.objects.get(user=self.agent2)
        agent2_wallet.upcoming_payments = (
            self.app3.scholarship.agent_commission +
            self.app11.scholarship.agent_commission
        )
        agent2_wallet.save()

        # HQ2 upcoming for in-progress apps
        hq2_wallet = Wallet.objects.get(user=self.hq2)
        hq2_wallet.upcoming_payments = (
            self.app3.scholarship.hq_commission +
            self.app11.scholarship.hq_commission +
            self.app12.scholarship.hq_commission
        )
        hq2_wallet.save()

    # ------------------------------------------------------------------ #
    #  8. Notifications
    # ------------------------------------------------------------------ #
    def _create_notifications(self):
        self.stdout.write("Creating notifications …")

        notifs = [
            # Student notifications
            (self.student1, "Application Complete! 🎉",
             f"Your application for {self.app1.scholarship.name} has been completed. All documents are ready.",
             "/scholarships/application/1/", False, 27),
            (self.student2, "Application Approved",
             f"Congratulations! Your application for {self.app2.scholarship.name} has been approved.",
             "/scholarships/application/2/", False, 22),
            (self.student3, "Application In Progress",
             f"Your application for {self.app3.scholarship.name} is being processed by our agent.",
             "/scholarships/application/3/", True, 34),
            (self.student4, "Application Submitted",
             "Your application has been submitted and is awaiting review.",
             "/scholarships/application/4/", False, 5),
            (self.student5, "Under Review",
             f"Your {self.app5.scholarship.name} application is now under review.",
             "/scholarships/application/5/", True, 8),
            (self.student6, "Application Rejected",
             f"Unfortunately, your application for {self.app6.scholarship.name} was rejected. Reason: Incomplete documents.",
             "/scholarships/application/6/", False, 16),

            # Office notifications
            (self.office1, "New Application Received",
             f"Omar Khan submitted an application for {self.app4.scholarship.name}.",
             "/office/applications/", False, 5),
            (self.office1, "Payment Receipt Uploaded",
             f"Maria Garcia uploaded a payment receipt for {self.app8.scholarship.name}.",
             "/office/payments/", False, 11),

            # Agent notifications
            (self.agent1, "New Assignment",
             f"You have been assigned to {self.student2.first_name}'s application for {self.app2.scholarship.name}.",
             "/agent/applications/", False, 22),
            (self.agent1, "Admission Letter Uploaded",
             f"HQ uploaded an admission letter for {self.student3.first_name}'s application.",
             "/agent/applications/", True, 15),
            (self.agent1, "Withdrawal Request Submitted",
             "Your withdrawal request for $100.00 has been submitted and is pending admin approval.",
             "/agent/wallet/", False, 3),

            # HQ notifications
            (self.hq1, "Commission Earned 💰",
             f"You earned ${self.app1.scholarship.hq_commission} commission for {self.app1.scholarship.name}.",
             "/headquarters/wallet/", True, 27),
            (self.hq2, "New Application Assigned",
             f"You have been assigned to process {self.student3.first_name}'s application for {self.app3.scholarship.name}.",
             "/headquarters/applications/", False, 34),
        ]

        for user, title, message, link, is_read, days_ago in notifs:
            n = Notification.objects.create(
                user=user,
                title=title,
                message=message,
                link=link,
                is_read=is_read,
            )
            Notification.objects.filter(pk=n.pk).update(
                created_at=self._past(days=days_ago)
            )

    # ------------------------------------------------------------------ #
    #  Summary
    # ------------------------------------------------------------------ #
    def _print_summary(self):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("  DATA SUMMARY")
        self.stdout.write("=" * 60)
        self.stdout.write(f"  Users:              {User.objects.count()}")
        self.stdout.write(f"    - Students:       {User.objects.filter(role='user').count()}")
        self.stdout.write(f"    - Office:         {User.objects.filter(role='office').count()}")
        self.stdout.write(f"    - Agents:         {User.objects.filter(role='agent').count()}")
        self.stdout.write(f"    - HQ:             {User.objects.filter(role='headquarters').count()}")
        self.stdout.write(f"  Scholarships:       {scholarships.objects.count()}")
        self.stdout.write(f"  Applications:       {Application.objects.count()}")
        self.stdout.write(f"  Status History:     {ApplicationStatusHistory.objects.count()}")
        self.stdout.write(f"  Payments:           {application_payment.objects.count()}")
        self.stdout.write(f"  Bank Accounts:      {bank_account.objects.count()}")
        self.stdout.write(f"  Wallets:            {Wallet.objects.count()}")
        self.stdout.write(f"  Transactions:       {WalletTransaction.objects.count()}")
        self.stdout.write(f"  Withdrawals:        {WithdrawalRequest.objects.count()}")
        self.stdout.write(f"  Notifications:      {Notification.objects.count()}")
        self.stdout.write("=" * 60)
        self.stdout.write("\n  LOGIN CREDENTIALS")
        self.stdout.write("-" * 60)
        self.stdout.write("  Role          Username         Password")
        self.stdout.write("-" * 60)
        self.stdout.write("  Admin         admin            admin123")
        self.stdout.write("  Office        sarah_office     office123")
        self.stdout.write("  Office        mike_office      office123")
        self.stdout.write("  Agent         li_agent         agent123")
        self.stdout.write("  Agent         ahmed_agent      agent123")
        self.stdout.write("  HQ            chen_hq          hq123")
        self.stdout.write("  HQ            wang_hq          hq123")
        self.stdout.write("  Student       john_doe         student123")
        self.stdout.write("  Student       maria_garcia     student123")
        self.stdout.write("  Student       fatima_ali       student123")
        self.stdout.write("  Student       omar_khan        student123")
        self.stdout.write("  Student       yuki_tanaka      student123")
        self.stdout.write("  Student       david_kim        student123")
        self.stdout.write("=" * 60)
