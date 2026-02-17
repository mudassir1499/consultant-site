"""
Wallet business logic for commission tracking and withdrawals.

Commission flow:
1. Agent approves admission letter → agent_commission added to Agent's upcoming,
   hq_commission added to HQ's upcoming
2. Agent approves JW02 → both commissions move from upcoming to current_balance
3. User requests withdrawal (≥$100) → amount moves from balance to pending_withdrawals
4. Admin approves → amount moves from pending_withdrawals to total_withdrawn
5. Admin rejects → amount returns from pending_withdrawals to current_balance
"""

from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from .models import Wallet, WalletTransaction, WithdrawalRequest


def get_or_create_wallet(user):
    """Get or create a wallet for a user (agent or headquarters)"""
    wallet, created = Wallet.objects.get_or_create(user=user)
    return wallet


@transaction.atomic
def add_upcoming_payments(application):
    """
    Called when Agent approves an admission letter.
    Adds commission to both Agent's and HQ's upcoming_payments.
    """
    scholarship = application.scholarship
    results = {}

    # Agent commission
    if application.assigned_agent and scholarship.agent_commission > 0:
        agent_wallet = get_or_create_wallet(application.assigned_agent)
        agent_wallet.upcoming_payments += scholarship.agent_commission
        agent_wallet.save()
        WalletTransaction.objects.create(
            wallet=agent_wallet,
            application=application,
            type='earning',
            amount=scholarship.agent_commission,
            description=f"Upcoming: Admission letter approved for {application.scholarship.name} (App #{application.app_id})",
            status='pending',
        )
        results['agent'] = scholarship.agent_commission

    # HQ commission
    if application.assigned_hq and scholarship.hq_commission > 0:
        hq_wallet = get_or_create_wallet(application.assigned_hq)
        hq_wallet.upcoming_payments += scholarship.hq_commission
        hq_wallet.save()
        WalletTransaction.objects.create(
            wallet=hq_wallet,
            application=application,
            type='earning',
            amount=scholarship.hq_commission,
            description=f"Upcoming: Admission letter approved for {application.scholarship.name} (App #{application.app_id})",
            status='pending',
        )
        results['hq'] = scholarship.hq_commission

    return results


@transaction.atomic
def move_to_balance(application):
    """
    Called when Agent approves JW02 form.
    Moves commission from upcoming_payments to current_balance for both Agent and HQ.
    """
    scholarship = application.scholarship
    results = {}

    # Agent
    if application.assigned_agent and scholarship.agent_commission > 0:
        agent_wallet = get_or_create_wallet(application.assigned_agent)
        agent_wallet.upcoming_payments -= scholarship.agent_commission
        agent_wallet.current_balance += scholarship.agent_commission
        agent_wallet.total_earned += scholarship.agent_commission
        agent_wallet.save()
        # Update the pending transaction to completed
        WalletTransaction.objects.filter(
            wallet=agent_wallet,
            application=application,
            type='earning',
            status='pending',
        ).update(status='completed')
        WalletTransaction.objects.create(
            wallet=agent_wallet,
            application=application,
            type='balance_transfer',
            amount=scholarship.agent_commission,
            description=f"JW02 approved: ${scholarship.agent_commission} moved to balance for {application.scholarship.name} (App #{application.app_id})",
            status='completed',
        )
        results['agent'] = scholarship.agent_commission

    # HQ
    if application.assigned_hq and scholarship.hq_commission > 0:
        hq_wallet = get_or_create_wallet(application.assigned_hq)
        hq_wallet.upcoming_payments -= scholarship.hq_commission
        hq_wallet.current_balance += scholarship.hq_commission
        hq_wallet.total_earned += scholarship.hq_commission
        hq_wallet.save()
        WalletTransaction.objects.filter(
            wallet=hq_wallet,
            application=application,
            type='earning',
            status='pending',
        ).update(status='completed')
        WalletTransaction.objects.create(
            wallet=hq_wallet,
            application=application,
            type='balance_transfer',
            amount=scholarship.hq_commission,
            description=f"JW02 approved: ${scholarship.hq_commission} moved to balance for {application.scholarship.name} (App #{application.app_id})",
            status='completed',
        )
        results['hq'] = scholarship.hq_commission

    return results


@transaction.atomic
def request_withdrawal(wallet, amount):
    """
    User requests a withdrawal. Minimum $100.
    Moves amount from current_balance to pending_withdrawals.
    """
    amount = Decimal(str(amount))
    if amount < Decimal('100.00'):
        raise ValueError("Minimum withdrawal amount is $100.00")
    if wallet.current_balance < amount:
        raise ValueError("Insufficient balance")

    wallet.current_balance -= amount
    wallet.pending_withdrawals += amount
    wallet.save()

    withdrawal = WithdrawalRequest.objects.create(
        wallet=wallet,
        amount=amount,
        status='pending',
    )

    WalletTransaction.objects.create(
        wallet=wallet,
        type='withdrawal',
        amount=amount,
        description=f"Withdrawal request #{withdrawal.id} - ${amount}",
        status='pending',
    )

    return withdrawal


@transaction.atomic
def approve_withdrawal(withdrawal_request, admin_user):
    """Admin approves a withdrawal request. Deducts from pending_withdrawals, adds to total_withdrawn."""
    if withdrawal_request.status != 'pending':
        raise ValueError("Can only approve pending withdrawal requests")

    wallet = withdrawal_request.wallet
    wallet.pending_withdrawals -= withdrawal_request.amount
    wallet.total_withdrawn += withdrawal_request.amount
    wallet.save()

    withdrawal_request.status = 'approved'
    withdrawal_request.processed_at = timezone.now()
    withdrawal_request.processed_by = admin_user
    withdrawal_request.save()

    # Update the pending transaction
    WalletTransaction.objects.filter(
        wallet=wallet,
        type='withdrawal',
        status='pending',
        amount=withdrawal_request.amount,
        description__contains=f"#{withdrawal_request.id}",
    ).update(status='completed')

    return withdrawal_request


@transaction.atomic
def reject_withdrawal(withdrawal_request, admin_user, reason=''):
    """Admin rejects a withdrawal request. Returns amount from pending_withdrawals to current_balance."""
    if withdrawal_request.status != 'pending':
        raise ValueError("Can only reject pending withdrawal requests")

    wallet = withdrawal_request.wallet
    wallet.pending_withdrawals -= withdrawal_request.amount
    wallet.current_balance += withdrawal_request.amount
    wallet.save()

    withdrawal_request.status = 'rejected'
    withdrawal_request.rejection_reason = reason
    withdrawal_request.processed_at = timezone.now()
    withdrawal_request.processed_by = admin_user
    withdrawal_request.save()

    # Update the pending transaction to cancelled
    WalletTransaction.objects.filter(
        wallet=wallet,
        type='withdrawal',
        status='pending',
        amount=withdrawal_request.amount,
        description__contains=f"#{withdrawal_request.id}",
    ).update(status='cancelled')

    return withdrawal_request
