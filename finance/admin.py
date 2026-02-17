from django.contrib import admin
from django.utils import timezone
from .models import bank_account, application_payment, Wallet, WalletTransaction, WithdrawalRequest


@admin.register(bank_account)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['bank_name', 'account_number', 'account_holder_name', 'swift_code', 'status']
    list_filter = ['status', 'created_at']
    search_fields = ['bank_name', 'account_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(application_payment)
class ApplicationPaymentAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'application', 'amount', 'payment_status', 'payment_date']
    list_filter = ['payment_status', 'payment_date']
    search_fields = ['transaction_id', 'application__user__username']
    readonly_fields = ['payment_date']


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_role', 'current_balance', 'upcoming_payments', 'pending_withdrawals', 'total_earned', 'total_withdrawn']
    list_filter = ['user__role']
    search_fields = ['user__username']
    readonly_fields = ['user', 'current_balance', 'upcoming_payments', 'pending_withdrawals', 'total_earned', 'total_withdrawn', 'created_at', 'updated_at']

    def get_role(self, obj):
        return obj.user.get_role_display()
    get_role.short_description = 'Role'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'type', 'amount', 'description', 'status', 'created_at']
    list_filter = ['type', 'status', 'created_at']
    search_fields = ['wallet__user__username', 'description']
    readonly_fields = ['wallet', 'application', 'type', 'amount', 'description', 'status', 'created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'amount', 'status', 'requested_at', 'processed_at', 'processed_by']
    list_filter = ['status', 'requested_at']
    search_fields = ['wallet__user__username']
    readonly_fields = ['wallet', 'amount', 'requested_at', 'processed_at', 'processed_by']
    actions = ['approve_withdrawals', 'reject_withdrawals']

    @admin.action(description='Approve selected withdrawal requests')
    def approve_withdrawals(self, request, queryset):
        from .services import approve_withdrawal
        from users.notifications import send_notification
        count = 0
        for withdrawal in queryset.filter(status='pending'):
            try:
                approve_withdrawal(withdrawal, request.user)
                send_notification(
                    withdrawal.wallet.user,
                    'Withdrawal Approved',
                    f'Your withdrawal request of ${withdrawal.amount} has been approved.',
                    link='/agent/wallet/' if withdrawal.wallet.user.role == 'agent' else '/hq/wallet/'
                )
                count += 1
            except Exception as e:
                self.message_user(request, f'Error approving withdrawal {withdrawal.id}: {e}', level='error')
        self.message_user(request, f'{count} withdrawal(s) approved.')

    @admin.action(description='Reject selected withdrawal requests')
    def reject_withdrawals(self, request, queryset):
        from .services import reject_withdrawal
        from users.notifications import send_notification
        count = 0
        for withdrawal in queryset.filter(status='pending'):
            try:
                reject_withdrawal(withdrawal, request.user, 'Rejected by admin')
                send_notification(
                    withdrawal.wallet.user,
                    'Withdrawal Rejected',
                    f'Your withdrawal request of ${withdrawal.amount} was rejected. Reason: Rejected by admin',
                    link='/agent/wallet/' if withdrawal.wallet.user.role == 'agent' else '/hq/wallet/'
                )
                count += 1
            except Exception as e:
                self.message_user(request, f'Error rejecting withdrawal {withdrawal.id}: {e}', level='error')
        self.message_user(request, f'{count} withdrawal(s) rejected.')
