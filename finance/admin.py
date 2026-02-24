from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import bank_account, application_payment, Wallet, WalletTransaction, WithdrawalRequest


@admin.register(bank_account)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['bank_name', 'account_holder_name', 'account_number_masked', 'swift_code', 'status_badge']
    list_filter = ['status', 'created_at']
    search_fields = ['bank_name', 'account_number', 'account_holder_name']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25

    fieldsets = (
        (None, {
            'fields': ('bank_name', 'account_holder_name', 'status'),
            'description': (
                '<strong>🏦 Bank Account Management</strong><br>'
                'These are the company bank accounts displayed to students for payment. '
                'Only <strong>Active</strong> accounts are shown on the payment page.'
            ),
        }),
        ('Account Details', {
            'fields': ('account_number', 'iban', 'swift_code'),
            'description': 'Full account details. Ensure SWIFT code is correct for international transfers.',
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def account_number_masked(self, obj):
        num = obj.account_number
        if len(num) > 6:
            return f'****{num[-4:]}'
        return num
    account_number_masked.short_description = 'Account #'

    def status_badge(self, obj):
        color = '#198754' if obj.status == 'active' else '#dc3545'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'


@admin.register(application_payment)
class ApplicationPaymentAdmin(admin.ModelAdmin):
    list_display = ['transaction_id_display', 'application_link', 'amount_display', 'status_badge', 'receipt_link', 'payment_date', 'reviewed_by']
    list_filter = ['payment_status', 'payment_date']
    search_fields = ['transaction_id', 'application__user__username', 'application__app_id']
    readonly_fields = ['payment_date', 'receipt_preview']
    list_per_page = 30
    date_hierarchy = 'payment_date'
    actions = ['approve_payments', 'reject_payments']

    fieldsets = (
        (None, {
            'fields': ('application', 'amount', 'transaction_id', 'payment_status'),
            'description': (
                '<strong>💳 Payment Record</strong><br>'
                'Each payment is linked to a scholarship application. '
                'Payments are created when a student or office worker uploads a receipt.'
            ),
        }),
        ('📄 Receipt', {
            'fields': ('receipt_pdf', 'receipt_preview'),
            'description': 'The uploaded payment receipt (PDF, JPG, or PNG).',
        }),
        ('✅ Review', {
            'fields': ('reviewed_by', 'reviewed_at', 'review_note'),
            'description': 'Review details. Only completed after an office worker approves or rejects the payment.',
        }),
        ('Metadata', {
            'fields': ('payment_date',),
            'classes': ('collapse',),
        }),
    )

    def transaction_id_display(self, obj):
        return obj.transaction_id or format_html('<em style="color:#999;">N/A</em>')
    transaction_id_display.short_description = 'Transaction ID'

    def application_link(self, obj):
        return format_html(
            '<a href="/admin/scholarships/application/{}/change/">#{} — {}</a>',
            obj.application.app_id, obj.application.app_id,
            obj.application.user.username,
        )
    application_link.short_description = 'Application'

    def amount_display(self, obj):
        return format_html('<strong>${:,.2f}</strong>', obj.amount)
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'

    PAYMENT_COLORS = {
        'pending': '#fd7e14', 'processing': '#0dcaf0', 'under_review': '#6610f2',
        'completed': '#198754', 'failed': '#dc3545',
    }

    def status_badge(self, obj):
        color = self.PAYMENT_COLORS.get(obj.payment_status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;">{}</span>',
            color, obj.get_payment_status_display(),
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'payment_status'

    def receipt_link(self, obj):
        if obj.receipt_pdf:
            return format_html('<a href="{}" target="_blank">📎 View</a>', obj.receipt_pdf.url)
        return '—'
    receipt_link.short_description = 'Receipt'

    def receipt_preview(self, obj):
        if obj.receipt_pdf:
            url = obj.receipt_pdf.url
            if url.lower().endswith(('.jpg', '.jpeg', '.png')):
                return format_html(
                    '<a href="{url}" target="_blank"><img src="{url}" style="max-height:200px;border:1px solid #ddd;border-radius:4px;" /></a>',
                    url=url,
                )
            return format_html('<a href="{}" target="_blank" class="button">📎 Download Receipt</a>', url)
        return '(No receipt uploaded)'
    receipt_preview.short_description = 'Receipt Preview'

    @admin.action(description='✅ Approve selected payments')
    def approve_payments(self, request, queryset):
        count = 0
        for p in queryset.filter(payment_status__in=['pending', 'under_review', 'processing']):
            p.payment_status = 'completed'
            p.reviewed_by = request.user
            p.reviewed_at = timezone.now()
            p.review_note = p.review_note or 'Approved by admin'
            p.save()
            count += 1
        self.message_user(request, f'{count} payment(s) approved.')

    @admin.action(description='❌ Reject selected payments')
    def reject_payments(self, request, queryset):
        count = 0
        for p in queryset.filter(payment_status__in=['pending', 'under_review', 'processing']):
            p.payment_status = 'failed'
            p.reviewed_by = request.user
            p.reviewed_at = timezone.now()
            p.review_note = p.review_note or 'Rejected by admin'
            p.save()
            count += 1
        self.message_user(request, f'{count} payment(s) rejected.')


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'role_badge', 'balance_display', 'upcoming_display', 'pending_display', 'total_earned_display', 'total_withdrawn_display']
    list_filter = ['user__role']
    search_fields = ['user__username']
    readonly_fields = ['user', 'current_balance', 'upcoming_payments', 'pending_withdrawals', 'total_earned', 'total_withdrawn', 'created_at', 'updated_at']
    list_per_page = 25

    fieldsets = (
        (None, {
            'fields': ('user',),
            'description': (
                '<strong>💰 Wallet Overview</strong><br>'
                'Wallets are created automatically for agents and HQ users. '
                'Commissions flow as: Upcoming → Balance (on approval) → Withdrawn (on payout).<br>'
                '<em>Wallets are read-only. Balances are updated automatically by the system.</em>'
            ),
        }),
        ('💵 Balances', {
            'fields': ('current_balance', 'upcoming_payments', 'pending_withdrawals'),
            'description': (
                '<strong>Balance:</strong> Available for withdrawal.<br>'
                '<strong>Upcoming:</strong> Earned but not yet released (pending final approval).<br>'
                '<strong>Pending Withdrawals:</strong> Withdrawal requests awaiting admin approval.'
            ),
        }),
        ('📊 Totals', {
            'fields': ('total_earned', 'total_withdrawn'),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def role_badge(self, obj):
        colors = {'agent': '#fd7e14', 'headquarters': '#6f42c1'}
        color = colors.get(obj.user.role, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;">{}</span>',
            color, obj.user.get_role_display(),
        )
    role_badge.short_description = 'Role'

    def balance_display(self, obj):
        return format_html('<strong style="color:#198754;">${:,.2f}</strong>', obj.current_balance)
    balance_display.short_description = 'Balance'

    def upcoming_display(self, obj):
        return format_html('${:,.2f}', obj.upcoming_payments)
    upcoming_display.short_description = 'Upcoming'

    def pending_display(self, obj):
        if obj.pending_withdrawals > 0:
            return format_html('<span style="color:#fd7e14;">${:,.2f}</span>', obj.pending_withdrawals)
        return '$0.00'
    pending_display.short_description = 'Pending W/D'

    def total_earned_display(self, obj):
        return format_html('${:,.2f}', obj.total_earned)
    total_earned_display.short_description = 'Total Earned'

    def total_withdrawn_display(self, obj):
        return format_html('${:,.2f}', obj.total_withdrawn)
    total_withdrawn_display.short_description = 'Total Withdrawn'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'type_badge', 'amount_display', 'description_preview', 'status_badge', 'created_at']
    list_filter = ['type', 'status', 'created_at']
    search_fields = ['wallet__user__username', 'description']
    readonly_fields = ['wallet', 'application', 'type', 'amount', 'description', 'status', 'created_at']
    list_per_page = 50
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('wallet', 'application', 'type', 'amount', 'status', 'description'),
            'description': (
                'Transaction log for wallet movements. '
                'These records are created automatically and cannot be modified.'
            ),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def type_badge(self, obj):
        colors = {'commission': '#198754', 'withdrawal': '#0d6efd', 'adjustment': '#fd7e14'}
        color = colors.get(obj.type, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;">{}</span>',
            color, obj.get_type_display(),
        )
    type_badge.short_description = 'Type'

    def amount_display(self, obj):
        return format_html('<strong>${:,.2f}</strong>', obj.amount)
    amount_display.short_description = 'Amount'

    def description_preview(self, obj):
        if obj.description:
            return obj.description[:50] + '…' if len(obj.description) > 50 else obj.description
        return '—'
    description_preview.short_description = 'Description'

    def status_badge(self, obj):
        colors = {'upcoming': '#fd7e14', 'completed': '#198754', 'cancelled': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ['wallet_user', 'amount_display', 'status_badge', 'requested_at', 'processed_at', 'processed_by']
    list_filter = ['status', 'requested_at']
    search_fields = ['wallet__user__username']
    readonly_fields = ['wallet', 'amount', 'requested_at', 'processed_at', 'processed_by']
    list_per_page = 30
    date_hierarchy = 'requested_at'
    actions = ['approve_withdrawals', 'reject_withdrawals']

    fieldsets = (
        (None, {
            'fields': ('wallet', 'amount', 'status'),
            'description': (
                '<strong>🏧 Withdrawal Request</strong><br>'
                'Users request withdrawals from their wallet balance. '
                'Use the <strong>Actions</strong> dropdown on the list page to approve or reject in bulk, '
                'or change the status here for individual requests.'
            ),
        }),
        ('📝 Admin Notes', {
            'fields': ('note',),
            'description': 'Optional reason for approval/rejection. Visible to the requesting user.',
        }),
        ('Processing Info', {
            'fields': ('requested_at', 'processed_at', 'processed_by'),
            'classes': ('collapse',),
            'description': 'Auto-populated when the request is processed.',
        }),
    )

    def wallet_user(self, obj):
        return format_html(
            '<a href="/admin/finance/wallet/{}/change/">{}</a>',
            obj.wallet.pk, obj.wallet.user.username,
        )
    wallet_user.short_description = 'User'

    def amount_display(self, obj):
        return format_html('<strong>${:,.2f}</strong>', obj.amount)
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'

    def status_badge(self, obj):
        colors = {
            'pending': '#fd7e14', 'approved': '#198754',
            'rejected': '#dc3545', 'processing': '#0dcaf0',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'

    @admin.action(description='✅ Approve selected withdrawal requests')
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

    @admin.action(description='❌ Reject selected withdrawal requests')
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
