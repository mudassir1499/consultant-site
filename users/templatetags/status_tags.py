"""
Custom template tags for status badges, time formatting, and utility filters.
Usage: {% load status_tags %}
"""

from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()

# ─── Application Status → Bootstrap badge mapping ───────────────────
STATUS_BADGE_MAP = {
    'draft': ('secondary', 'bi-pencil'),
    'submitted': ('warning text-dark', 'bi-send-check'),
    'under_review': ('info', 'bi-search'),
    'documents_verified': ('primary', 'bi-file-earmark-check'),
    'payment_verified': ('primary', 'bi-patch-check'),
    'approved': ('success', 'bi-hand-thumbs-up'),
    'in_progress': ('info', 'bi-gear'),
    'admission_letter_uploaded': ('primary', 'bi-envelope-paper'),
    'admission_letter_approved': ('success', 'bi-envelope-check'),
    'jw02_uploaded': ('primary', 'bi-file-earmark-ruled'),
    'jw02_approved': ('success', 'bi-file-earmark-check'),
    'complete': ('dark', 'bi-trophy'),
    'rejected': ('danger', 'bi-x-circle'),
    'letter_pending': ('warning text-dark', 'bi-exclamation-triangle'),
    'jw02_pending': ('warning text-dark', 'bi-exclamation-triangle'),
}

# Payment status mapping
PAYMENT_BADGE_MAP = {
    'pending': ('warning text-dark', 'bi-clock'),
    'processing': ('info', 'bi-arrow-repeat'),
    'under_review': ('info', 'bi-search'),
    'completed': ('success', 'bi-check-circle'),
    'failed': ('danger', 'bi-x-circle'),
}

# Status display labels (fallback if model doesn't provide get_status_display)
STATUS_LABELS = {
    'draft': 'Draft',
    'submitted': 'Submitted',
    'under_review': 'Under Review',
    'documents_verified': 'Documents Verified',
    'payment_verified': 'Payment Verified',
    'approved': 'Approved',
    'in_progress': 'In Progress',
    'admission_letter_uploaded': 'Letter Uploaded',
    'admission_letter_approved': 'Letter Approved',
    'jw02_uploaded': 'JW02 Uploaded',
    'jw02_approved': 'JW02 Approved',
    'complete': 'Complete',
    'rejected': 'Rejected',
    'letter_pending': 'Letter Pending',
    'jw02_pending': 'JW02 Pending',
}


@register.simple_tag
def status_badge(status, size='normal'):
    """
    Render a Bootstrap badge for an application status.
    Usage: {% status_badge app.status %} or {% status_badge app.status 'small' %}
    """
    badge_class, icon = STATUS_BADGE_MAP.get(status, ('secondary', 'bi-question-circle'))
    label = STATUS_LABELS.get(status, status.replace('_', ' ').title())
    size_class = 'badge-status' if size == 'small' else ''
    return mark_safe(
        f'<span class="badge bg-{badge_class} {size_class}">'
        f'<i class="bi {icon} me-1"></i>{label}</span>'
    )


@register.simple_tag
def payment_badge(status):
    """Render a Bootstrap badge for a payment status."""
    badge_class, icon = PAYMENT_BADGE_MAP.get(status, ('secondary', 'bi-question-circle'))
    label = status.replace('_', ' ').title()
    return mark_safe(
        f'<span class="badge bg-{badge_class}">'
        f'<i class="bi {icon} me-1"></i>{label}</span>'
    )


@register.filter
def time_ago(value):
    """
    Convert a datetime to a human-readable relative time string.
    Usage: {{ some_datetime|time_ago }}
    """
    if not value:
        return ''
    now = timezone.now()
    diff = now - value

    seconds = diff.total_seconds()
    if seconds < 0:
        return 'just now'
    if seconds < 60:
        return 'just now'
    elif seconds < 3600:
        m = int(seconds / 60)
        return f'{m} min{"s" if m != 1 else ""} ago'
    elif seconds < 86400:
        h = int(seconds / 3600)
        return f'{h} hour{"s" if h != 1 else ""} ago'
    elif seconds < 172800:
        return 'yesterday'
    elif seconds < 604800:
        d = int(seconds / 86400)
        return f'{d} days ago'
    elif seconds < 2592000:
        w = int(seconds / 604800)
        return f'{w} week{"s" if w != 1 else ""} ago'
    else:
        return value.strftime('%b %d, %Y')


@register.filter
def status_color(status):
    """Return just the Bootstrap color class for a status (no badge HTML)."""
    badge_class, _ = STATUS_BADGE_MAP.get(status, ('secondary', ''))
    return badge_class.split()[0]  # Return only first class (e.g., 'warning' not 'warning text-dark')


@register.filter
def status_icon(status):
    """Return the Bootstrap icon class for a status."""
    _, icon = STATUS_BADGE_MAP.get(status, ('', 'bi-question-circle'))
    return icon
