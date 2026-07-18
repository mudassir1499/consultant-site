"""Unit tests for wallet business logic (commissions & withdrawals)."""
from decimal import Decimal

from django.test import TestCase

from users.models import User
from finance.models import Wallet
from finance.services import (
    get_or_create_wallet, request_withdrawal, approve_withdrawal, reject_withdrawal,
)


class WalletServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="agent1", password="pw", role="agent")
        self.admin = User.objects.create_superuser(username="admin1", password="pw")
        self.wallet = get_or_create_wallet(self.user)
        self.wallet.current_balance = Decimal("500")
        self.wallet.save()

    def test_get_or_create_wallet_is_idempotent(self):
        w1 = get_or_create_wallet(self.user)
        w2 = get_or_create_wallet(self.user)
        self.assertEqual(w1.pk, w2.pk)
        self.assertEqual(Wallet.objects.filter(user=self.user).count(), 1)

    def test_withdrawal_below_minimum_rejected(self):
        with self.assertRaises(ValueError):
            request_withdrawal(self.wallet, "50")

    def test_withdrawal_over_balance_rejected(self):
        with self.assertRaises(ValueError):
            request_withdrawal(self.wallet, "600")

    def test_request_withdrawal_moves_to_pending(self):
        wd = request_withdrawal(self.wallet, "200")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("300"))
        self.assertEqual(self.wallet.pending_withdrawals, Decimal("200"))
        self.assertEqual(wd.status, "pending")

    def test_approve_withdrawal(self):
        wd = request_withdrawal(self.wallet, "200")
        approve_withdrawal(wd, self.admin)
        self.wallet.refresh_from_db()
        wd.refresh_from_db()
        self.assertEqual(wd.status, "approved")
        self.assertEqual(self.wallet.pending_withdrawals, Decimal("0"))
        self.assertEqual(self.wallet.total_withdrawn, Decimal("200"))
        self.assertEqual(self.wallet.current_balance, Decimal("300"))

    def test_reject_withdrawal_returns_balance(self):
        wd = request_withdrawal(self.wallet, "200")
        reject_withdrawal(wd, self.admin, reason="bad details")
        self.wallet.refresh_from_db()
        wd.refresh_from_db()
        self.assertEqual(wd.status, "rejected")
        self.assertEqual(self.wallet.pending_withdrawals, Decimal("0"))
        self.assertEqual(self.wallet.current_balance, Decimal("500"))

    def test_cannot_reprocess_a_processed_withdrawal(self):
        wd = request_withdrawal(self.wallet, "200")
        approve_withdrawal(wd, self.admin)
        with self.assertRaises(ValueError):
            approve_withdrawal(wd, self.admin)
        with self.assertRaises(ValueError):
            reject_withdrawal(wd, self.admin)
