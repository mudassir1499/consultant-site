from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

def get_receipt_upload_path(instance, filename):
    """
    Generate receipt upload path with username prefix: username-app_id-receipt-filename
    """
    username = instance.application.user.username
    app_id = instance.application.app_id
    return f"payments/receipts/{username}-{app_id}-receipt-{filename}"


class bank_account(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    account_id = models.AutoField(primary_key=True)
    bank_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=50)
    account_holder_name = models.CharField(max_length=255)
    iban = models.CharField(max_length=50, blank=True, null=True)
    swift_code = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"
    
    class Meta:
        db_table = 'bank_accounts'


class application_payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('under_review', 'Under Review'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    application_payment_id = models.AutoField(primary_key=True)
    application = models.ForeignKey('scholarships.Application', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt_pdf = models.FileField(upload_to=get_receipt_upload_path)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_date = models.DateTimeField(auto_now_add=True)
    
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        blank=True, null=True, related_name='reviewed_payments'
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    review_note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Payment {self.transaction_id} for {self.application}"
    
    class Meta:
        db_table = 'application_payments'


class Wallet(models.Model):
    """Wallet for Agent and HQ users to track earnings and withdrawals"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet'
    )
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    upcoming_payments = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    pending_withdrawals = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet: {self.user.username} (Balance: ${self.current_balance})"

    class Meta:
        db_table = 'wallets'


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('earning', 'Earning'),
        ('withdrawal', 'Withdrawal'),
        ('balance_transfer', 'Balance Transfer'),
    ]
    TRANSACTION_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    application = models.ForeignKey(
        'scholarships.Application', on_delete=models.SET_NULL,
        blank=True, null=True, related_name='wallet_transactions'
    )
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='completed')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_type_display()} - ${self.amount} ({self.wallet.user.username})"

    class Meta:
        db_table = 'wallet_transactions'
        ordering = ['-created_at']


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('100.00'))],
        help_text="Minimum withdrawal amount is $100.00"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        blank=True, null=True, related_name='processed_withdrawals'
    )

    def __str__(self):
        return f"Withdrawal ${self.amount} by {self.wallet.user.username} - {self.get_status_display()}"

    class Meta:
        db_table = 'withdrawal_requests'
        ordering = ['-requested_at']