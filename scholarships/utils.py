"""
Application status transition helper with audit trail.
"""

from django.utils import timezone
from scholarships.models import ApplicationStatusHistory


def change_application_status(application, new_status, changed_by, note=None):
    """
    Change application status with audit trail logging.
    
    Args:
        application: Application instance
        new_status: The new status string
        changed_by: User who made the change
        note: Optional note explaining the change
    """
    old_status = application.status
    application.status = new_status

    # Set date fields for key milestones
    if new_status == 'approved':
        application.approved_date = timezone.now()
    elif new_status == 'complete':
        application.completed_date = timezone.now()

    application.save()

    # Create audit trail
    ApplicationStatusHistory.objects.create(
        application=application,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        note=note,
    )

    return application
