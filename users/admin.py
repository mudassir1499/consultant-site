from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django import forms
from .models import User, Notification


class StaffUserCreationForm(UserCreationForm):
    """Custom creation form that shows role, email, phone and sends a welcome email."""
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=User.role.field.choices, initial='user')
    phone = forms.CharField(required=False)
    send_welcome_email = forms.BooleanField(
        required=False, initial=True,
        label='Send welcome email with login credentials',
        help_text='If checked, the new user will receive an email with their username and a password reset link.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'phone')


class CustomUserAdmin(UserAdmin):
    model = User
    add_form = StaffUserCreationForm

    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'status', 'is_active', 'date_joined']
    list_filter = ['role', 'status', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone']
    list_editable = ['role', 'status']
    ordering = ['-date_joined']

    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'phone', 'status')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'first_name', 'last_name',
                'password1', 'password2',
                'role', 'phone', 'send_welcome_email',
            ),
        }),
    )

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
    list_display = ['user', 'title', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    readonly_fields = ['created_at']
