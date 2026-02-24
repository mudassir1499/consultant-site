from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.utils.html import format_html
from django import forms
from .models import User, Notification


class StaffUserCreationForm(UserCreationForm):
    """Custom creation form that shows role, email, phone and sends a welcome email."""
    email = forms.EmailField(required=True, help_text='Required. The user will receive a welcome email here.')
    role = forms.ChoiceField(
        choices=User.role.field.choices, initial='user',
        help_text='User = Student | Office = Branch worker | Main Agent = Reviews applications | Headquarters = University liaison',
    )
    phone = forms.CharField(required=False, help_text='Optional phone number with country code.')
    send_welcome_email = forms.BooleanField(
        required=False, initial=True,
        label='Send welcome email with login credentials',
        help_text='If checked, the new user will receive an email with their username and a password reset link.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'phone')


class ApplicationInline(admin.TabularInline):
    """Shows this user's applications inline."""
    from scholarships.models import Application
    model = Application
    fk_name = 'user'
    fields = ['app_id', 'scholarship', 'office', 'status', 'applied_date']
    readonly_fields = ['app_id', 'scholarship', 'office', 'status', 'applied_date']
    extra = 0
    show_change_link = True
    verbose_name = 'Application'
    verbose_name_plural = 'Student Applications'
    max_num = 0  # Don't allow adding from here

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('scholarship', 'office')


class CustomUserAdmin(UserAdmin):
    model = User
    add_form = StaffUserCreationForm

    list_display = ['username', 'email', 'full_name_display', 'role_badge', 'office_display', 'status_badge', 'city', 'country', 'date_joined']
    list_filter = ['role', 'status', 'is_active', 'office', 'country']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'city', 'country']
    ordering = ['-date_joined']
    raw_id_fields = ['office']
    list_per_page = 30
    save_on_top = True
    date_hierarchy = 'date_joined'

    fieldsets = (
        (None, {
            'fields': ('username', 'password'),
        }),
        ('👤 Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone'),
            'description': 'Basic personal details for this user.',
        }),
        ('🔐 Role & Status', {
            'fields': ('role', 'status'),
            'description': (
                '<strong>Roles:</strong><br>'
                '• <strong>User</strong> — Student applicant. Can apply for scholarships and track progress.<br>'
                '• <strong>Office</strong> — Branch office worker. Manages applications, reviews documents, forwards to agents.<br>'
                '• <strong>Main Agent</strong> — Reviews forwarded applications, approves/rejects, assigns to HQ.<br>'
                '• <strong>Headquarters</strong> — University liaison. Submits to universities, uploads admission letters & JW02 forms.<br><br>'
                '<strong>Status:</strong> Active = can login. Inactive/Suspended = blocked from login.'
            ),
        }),
        ('🏢 Office & Location', {
            'fields': ('office', 'city', 'country'),
            'description': (
                '<strong>For Staff (Office/Agent):</strong> Assign the branch office they work at. '
                'They will ONLY see applications and data from their assigned office.<br>'
                '<strong>For Students:</strong> Location is captured at registration and used for auto-routing to the correct office.'
            ),
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
            'description': 'Advanced Django permissions. Usually you only need to manage Role and Status above.',
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'first_name', 'last_name',
                'password1', 'password2',
                'role', 'phone', 'office', 'send_welcome_email',
            ),
            'description': (
                '<strong>📝 Creating a New User</strong><br>'
                '1. Fill in the username, email, and name.<br>'
                '2. Set a password (or share it via welcome email).<br>'
                '3. Choose the correct <strong>role</strong>.<br>'
                '4. For <strong>Office</strong> and <strong>Agent</strong> roles, assign an <strong>Office</strong> branch.<br>'
                '5. Check "Send welcome email" to notify them automatically.'
            ),
        }),
    )

    inlines = [ApplicationInline]

    def full_name_display(self, obj):
        name = obj.get_full_name()
        return name if name else format_html('<em style="color:#999;">—</em>')
    full_name_display.short_description = 'Name'
    full_name_display.admin_order_field = 'first_name'

    def role_badge(self, obj):
        colors = {
            'user': '#6c757d',
            'office': '#0d6efd',
            'agent': '#fd7e14',
            'headquarters': '#6f42c1',
        }
        color = colors.get(obj.role, '#6c757d')
        label = dict(User.role.field.choices).get(obj.role, obj.role)
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;white-space:nowrap;">{}</span>',
            color, label,
        )
    role_badge.short_description = 'Role'
    role_badge.admin_order_field = 'role'

    def status_badge(self, obj):
        colors = {'active': '#198754', 'inactive': '#dc3545', 'suspended': '#ffc107'}
        color = colors.get(obj.status, '#6c757d')
        text_color = '#000' if obj.status == 'suspended' else '#fff'
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;border-radius:10px;font-size:11px;">{}</span>',
            color, text_color, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def office_display(self, obj):
        if obj.office:
            return format_html('<a href="/admin/office/office/{}/change/">{}</a>', obj.office.pk, obj.office.name)
        if obj.role in ('office', 'agent'):
            return format_html('<span style="color:#dc3545;font-weight:bold;">⚠ Not assigned</span>')
        return '—'
    office_display.short_description = 'Office'
    office_display.admin_order_field = 'office'

    def save_model(self, request, obj, form, change):
        """Override save to send welcome email when creating new staff users."""
        super().save_model(request, obj, form, change)

        # Only send on creation (not edit) and if checkbox was checked
        if not change and form.cleaned_data.get('send_welcome_email') and obj.email:
            from django.contrib.auth.tokens import default_token_generator
            from django.utils.http import urlsafe_base64_encode
            from django.utils.encoding import force_bytes
            from django.core.mail import send_mail
            from django.conf import settings

            uid = urlsafe_base64_encode(force_bytes(obj.pk))
            token = default_token_generator.make_token(obj)
            domain = request.get_host()
            protocol = 'https' if request.is_secure() else 'http'
            reset_url = f"{protocol}://{domain}/users/password-reset-confirm/{uid}/{token}/"

            role_label = dict(User.role.field.choices).get(obj.role, obj.role)

            try:
                send_mail(
                    subject='EDU System - Your Account Has Been Created',
                    message=(
                        f"Hello {obj.get_full_name() or obj.username},\n\n"
                        f"An account has been created for you on the EDU System.\n\n"
                        f"Role: {role_label}\n"
                        f"Username: {obj.username}\n\n"
                        f"Please set your password using the link below:\n"
                        f"{reset_url}\n\n"
                        f"Thanks,\nEDU System Team"
                    ),
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@edu-system.com'),
                    recipient_list=[obj.email],
                    fail_silently=True,
                )
            except Exception:
                pass


admin.site.register(User, CustomUserAdmin)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'read_badge', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    readonly_fields = ['created_at']
    list_per_page = 50
    date_hierarchy = 'created_at'
    actions = ['mark_as_read', 'mark_as_unread']

    fieldsets = (
        (None, {
            'fields': ('user', 'title', 'message', 'link', 'is_read'),
            'description': 'In-app notifications sent to users. These appear in the notification bell within each portal.',
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def read_badge(self, obj):
        if obj.is_read:
            return format_html('<span style="color:#198754;">✓ Read</span>')
        return format_html('<span style="color:#0d6efd;font-weight:bold;">● Unread</span>')
    read_badge.short_description = 'Status'

    @admin.action(description='Mark selected as read')
    def mark_as_read(self, request, queryset):
        count = queryset.filter(is_read=False).update(is_read=True)
        self.message_user(request, f'{count} notification(s) marked as read.')

    @admin.action(description='Mark selected as unread')
    def mark_as_unread(self, request, queryset):
        count = queryset.filter(is_read=True).update(is_read=False)
        self.message_user(request, f'{count} notification(s) marked as unread.')
