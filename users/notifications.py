"""
Notification utility for sending in-app + email notifications.
"""

from django.core.mail import send_mail
from django.conf import settings
from .models import Notification


def send_notification(user, title, message, link=None):
    """
    Create an in-app notification and send an email.
    
    Args:
        user: The recipient User instance
        title: Short notification title
        message: Notification body text
        link: Optional URL to link to (relative path)
    """
    # Create in-app notification
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link,
    )

    # Send email (silently fail if email is not configured)
    try:
        if user.email:
            send_mail(
                subject=f"[EDU System] {title}",
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@edu-system.com'),
                recipient_list=[user.email],
                fail_silently=True,
            )
    except Exception:
        pass  # Email delivery failure should not break the workflow
