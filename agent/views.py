from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.db import models
from django.views.decorators.http import require_POST
from django.utils import timezone

from users.decorators import role_required
from users.models import User
from users.notifications import send_notification
from scholarships.models import Application, AdmissionLetter, JW02Form
from scholarships.utils import change_application_status
from finance.models import application_payment, Wallet
from finance.services import (
    get_or_create_wallet, add_upcoming_payments, move_to_balance,
    request_withdrawal as do_request_withdrawal,
)


# â”€â”€â”€ Agent Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def agent_login(request):
    """Separate login page for agents"""
    if request.user.is_authenticated and request.user.role == 'agent':
        return redirect('agent:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not all([username, password]):
            messages.error(request, 'Username and password are required.')
            return render(request, 'agent/login.html')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.role != 'agent':
                messages.error(request, 'This portal is for agents only.')
                return render(request, 'agent/login.html')
            if user.is_active:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                next_url = request.POST.get('next') or request.GET.get('next')
                return redirect(next_url or 'agent:dashboard')
            else:
                messages.error(request, 'Your account is inactive.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'agent/login.html')


@require_POST
def agent_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('agent:login')


@role_required('agent', login_url_override='agent:login')
def dashboard(request):
    """Agent dashboard with summary cards and wallet info"""
    user = request.user
    assigned = Application.objects.filter(assigned_agent=user).select_related('user', 'scholarship')
    wallet = get_or_create_wallet(user)

    # Group applications by status category for tabs
    pending_apps = assigned.filter(status__in=['submitted', 'payment_verified', 'documents_verified'])
    in_review_apps = assigned.filter(status='under_review')
    approved_apps = assigned.filter(status__in=['approved', 'in_progress'])
    letter_apps = assigned.filter(status__in=['admission_letter_uploaded', 'admission_letter_approved', 'letter_pending'])
    jw02_apps = assigned.filter(status__in=['jw02_uploaded', 'jw02_approved', 'jw02_pending'])
    completed_apps = assigned.filter(status='complete')
    rejected_apps = assigned.filter(status='rejected')

    context = {
        'user': user,
        'wallet': wallet,
        'total_assigned': assigned.count(),
        'pending_review': pending_apps.count(),
        'under_review': in_review_apps.count(),
        'approved_count': approved_apps.count(),
        'rejected_count': rejected_apps.count(),
        'pending_letters': assigned.filter(status='admission_letter_uploaded').count(),
        'pending_jw02': assigned.filter(status='jw02_uploaded').count(),
        'letter_count': letter_apps.count(),
        'jw02_count': jw02_apps.count(),
        'completed_count': completed_apps.count(),
        'all_applications': assigned.order_by('-applied_date'),
        'pending_apps': pending_apps.order_by('-applied_date'),
        'in_review_apps': in_review_apps.order_by('-applied_date'),
        'approved_apps': approved_apps.order_by('-applied_date'),
        'letter_apps': letter_apps.order_by('-applied_date'),
        'jw02_apps': jw02_apps.order_by('-applied_date'),
        'completed_apps': completed_apps.order_by('-applied_date'),
        'rejected_apps': rejected_apps.order_by('-applied_date'),
    }
    return render(request, 'agent/dashboard.html', context)


@role_required('agent', login_url_override='agent:login')
def application_list(request):
    """List all applications assigned to this agent"""
    user = request.user
    from django.db.models import Q
    
    all_apps = Application.objects.filter(
        assigned_agent=user
    ).select_related('user', 'scholarship').order_by('-applied_date')

    # Search filter
    query = request.GET.get('q', '').strip()
    if query:
        all_apps = all_apps.filter(
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(scholarship__name__icontains=query) |
            Q(app_id__icontains=query)
        )

    pending_apps = all_apps.filter(status__in=['submitted', 'payment_verified', 'documents_verified'])
    in_review_apps = all_apps.filter(status='under_review')
    approved_apps = all_apps.filter(status__in=['approved', 'in_progress'])
    letter_apps = all_apps.filter(status__in=['admission_letter_uploaded', 'admission_letter_approved', 'letter_pending'])
    jw02_apps = all_apps.filter(status__in=['jw02_uploaded', 'jw02_approved', 'jw02_pending'])
    completed_apps = all_apps.filter(status='complete')
    rejected_apps = all_apps.filter(status='rejected')

    context = {
        'user': user,
        'all_applications': all_apps,
        'search_query': query,
        'pending_apps': pending_apps,
        'in_review_apps': in_review_apps,
        'approved_apps': approved_apps,
        'letter_apps': letter_apps,
        'jw02_apps': jw02_apps,
        'completed_apps': completed_apps,
        'rejected_apps': rejected_apps,
        'total_count': all_apps.count(),
        'pending_count': pending_apps.count(),
        'review_count': in_review_apps.count(),
        'approved_count': approved_apps.count(),
        'letter_count': letter_apps.count(),
        'jw02_count': jw02_apps.count(),
        'completed_count': completed_apps.count(),
        'rejected_count': rejected_apps.count(),
    }
    return render(request, 'agent/application_list.html', context)


@role_required('agent', login_url_override='agent:login')
def application_detail(request, app_id):
    """Review application details â€” documents, payment, verification"""
    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_agent=user)
    payments = application_payment.objects.filter(application=application)
    status_history = application.status_history.all()[:20]

    documents = {
        'Photo': application.photo,
        'Passport': application.passport,
        'Graduation Certificate': application.graduation_certificate,
        'Criminal Record': application.criminal_record,
        'Medical Examination': application.medical_examination,
        'Recommendation Letter 1': application.letter_of_recommendation_1,
        'Recommendation Letter 2': application.letter_of_recommendation_2,
        'Study Plan': application.study_plan,
        'English Certificate': application.english_certificate,
    }

    context = {
        'user': user,
        'application': application,
        'payments': payments,
        'documents': documents,
        'status_history': status_history,
    }
    return render(request, 'agent/application_detail.html', context)


@role_required('agent', login_url_override='agent:login')
def approve_application(request, app_id):
    """Approve application â€” assign to HQ"""
    if request.method != 'POST':
        return redirect('agent:application_detail', app_id=app_id)

    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_agent=user)

    if application.status not in ('submitted', 'under_review', 'documents_verified', 'payment_verified'):
        messages.error(request, 'Application cannot be approved from its current status.')
        return redirect('agent:application_detail', app_id=app_id)

    # Get deadline from form
    from datetime import timedelta
    deadline_days = request.POST.get('deadline_days', '10')
    try:
        deadline_days = int(deadline_days)
        if deadline_days < 1:
            deadline_days = 10
    except (ValueError, TypeError):
        deadline_days = 10
    application.deadline = timezone.now() + timedelta(days=deadline_days)

    approve_note = request.POST.get('approve_note', '').strip()
    note_text = 'Application approved by agent'
    if approve_note:
        note_text += f' — Note: {approve_note}'

    # Assign HQ user (first available headquarters user, or admin can reassign)
    from users.models import User
    hq_user = User.objects.filter(role='headquarters', status='active').first()
    if hq_user:
        application.assigned_hq = hq_user

    change_application_status(application, 'approved', user, note=note_text)

    # Notify office worker
    send_notification(
        application.user,
        'Application Approved',
        f'Your application for {application.scholarship.name} has been approved.',
        link=f'/scholarships/application/{application.app_id}/'
    )

    # Notify HQ
    if hq_user:
        deadline_str = application.deadline.strftime('%b %d, %Y') if application.deadline else 'N/A'
        send_notification(
            hq_user,
            'New Application Assigned',
            f'Application #{application.app_id} for {application.scholarship.name} has been assigned to you. Deadline: {deadline_str}.',
            link=f'/hq/applications/{application.app_id}/'
        )

    messages.success(request, f'Application #{app_id} approved and forwarded to HQ. Deadline: {application.deadline.strftime("%b %d, %Y")}.')
    return redirect('agent:application_detail', app_id=app_id)


@role_required('agent', login_url_override='agent:login')
def reject_application(request, app_id):
    """Reject application with mandatory reason"""
    if request.method != 'POST':
        return redirect('agent:application_detail', app_id=app_id)

    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_agent=user)
    rejection_reason = request.POST.get('rejection_reason', '').strip()

    if not rejection_reason:
        messages.error(request, 'Rejection reason is required.')
        return redirect('agent:application_detail', app_id=app_id)

    application.rejection_reason = rejection_reason
    change_application_status(application, 'rejected', user, note=f'Rejected: {rejection_reason}')

    # Notify office worker / applicant
    send_notification(
        application.user,
        'Application Rejected',
        f'Your application for {application.scholarship.name} has been rejected. Reason: {rejection_reason}',
        link=f'/scholarships/application/{application.app_id}/'
    )

    messages.success(request, f'Application #{app_id} rejected.')
    return redirect('agent:application_detail', app_id=app_id)


@role_required('agent', login_url_override='agent:login')
def admission_letter_review(request, app_id):
    """Review admission letter uploaded by HQ"""
    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_agent=user)
    letter = application.admission_letters.filter(
        status='pending_verification'
    ).order_by('-uploaded_at').first()

    all_letters = application.admission_letters.all()

    context = {
        'user': user,
        'application': application,
        'letter': letter,
        'all_letters': all_letters,
    }
    return render(request, 'agent/admission_letter_review.html', context)


@role_required('agent', login_url_override='agent:login')
def approve_admission_letter(request, app_id):
    """Approve admission letter â€” triggers wallet upcoming payments"""
    if request.method != 'POST':
        return redirect('agent:admission_letter_review', app_id=app_id)

    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_agent=user)
    letter = application.admission_letters.filter(status='pending_verification').order_by('-uploaded_at').first()

    if not letter:
        messages.error(request, 'No pending admission letter to approve.')
        return redirect('agent:admission_letter_review', app_id=app_id)

    # Approve the letter
    letter.status = 'approved'
    letter.approved_at = timezone.now()
    letter.approved_by = user
    letter.save()

    change_application_status(application, 'admission_letter_approved', user, note='Admission letter approved')

    # Wallet action: add commissions to upcoming_payments
    add_upcoming_payments(application)

    # Notify HQ to upload JW02
    if application.assigned_hq:
        send_notification(
            application.assigned_hq,
            'Admission Letter Approved â€” Upload JW02',
            f'The admission letter for App #{application.app_id} ({application.scholarship.name}) has been approved. Please upload the JW02 form.',
            link=f'/hq/jw02/{application.app_id}/'
        )

    # Notify office worker
    send_notification(
        application.user,
        'Admission Letter Available',
        f'The admission letter for your application to {application.scholarship.name} is now available for download.',
        link=f'/scholarships/application/{application.app_id}/'
    )

    messages.success(request, 'Admission letter approved. Commissions added to upcoming payments.')
    return redirect('agent:admission_letter_review', app_id=app_id)


@role_required('agent', login_url_override='agent:login')
def request_revision(request, app_id):
    """Request revision of admission letter from HQ"""
    if request.method != 'POST':
        return redirect('agent:admission_letter_review', app_id=app_id)

    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_agent=user)
    revision_note = request.POST.get('revision_note', '').strip()

    if not revision_note:
        messages.error(request, 'Revision note is required.')
        return redirect('agent:admission_letter_review', app_id=app_id)

    letter = application.admission_letters.filter(status='pending_verification').order_by('-uploaded_at').first()
    if letter:
        letter.status = 'revision_requested'
        letter.revision_note = revision_note
        letter.save()

    change_application_status(application, 'letter_pending', user, note=f'Revision requested: {revision_note}')

    if application.assigned_hq:
        send_notification(
            application.assigned_hq,
            'Admission Letter Revision Required',
            f'App #{application.app_id}: The admission letter needs revision. Note: {revision_note}',
            link=f'/hq/revisions/'
        )

    messages.success(request, 'Revision request sent to HQ.')
    return redirect('agent:admission_letter_review', app_id=app_id)


@role_required('agent', login_url_override='agent:login')
def jw02_review(request, app_id):
    """Review JW02 form uploaded by HQ"""
    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_agent=user)
    jw02 = application.jw02_forms.filter(status='pending_verification').order_by('-uploaded_at').first()
    all_jw02s = application.jw02_forms.all()

    context = {
        'user': user,
        'application': application,
        'jw02': jw02,
        'all_jw02s': all_jw02s,
    }
    return render(request, 'agent/jw02_review.html', context)


@role_required('agent', login_url_override='agent:login')
def approve_jw02(request, app_id):
    """Approve JW02 form â€” moves commissions from upcoming to balance"""
    if request.method != 'POST':
        return redirect('agent:jw02_review', app_id=app_id)

    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_agent=user)
    jw02 = application.jw02_forms.filter(status='pending_verification').order_by('-uploaded_at').first()

    if not jw02:
        messages.error(request, 'No pending JW02 form to approve.')
        return redirect('agent:jw02_review', app_id=app_id)

    jw02.status = 'approved'
    jw02.approved_at = timezone.now()
    jw02.approved_by = user
    jw02.save()

    change_application_status(application, 'jw02_approved', user, note='JW02 form approved')

    # Mark application as complete
    change_application_status(application, 'complete', user, note='All documents approved â€” application complete')

    # Wallet action: move commissions from upcoming to balance
    move_to_balance(application)

    # Notify all parties
    if application.assigned_hq:
        send_notification(
            application.assigned_hq,
            'JW02 Approved â€” Commission Earned',
            f'Your JW02 form for App #{application.app_id} has been approved. Commission of ${application.scholarship.hq_commission} is now in your wallet balance.',
            link=f'/hq/wallet/'
        )

    send_notification(
        application.user,
        'Application Processing Complete',
        f'All documents for your application to {application.scholarship.name} have been processed.',
        link=f'/scholarships/application/{application.app_id}/'
    )

    messages.success(request, 'JW02 form approved. Commissions moved to wallet balance.')
    return redirect('agent:jw02_review', app_id=app_id)


@role_required('agent', login_url_override='agent:login')
def request_jw02_revision(request, app_id):
    """Request revision of JW02 form from HQ"""
    if request.method != 'POST':
        return redirect('agent:jw02_review', app_id=app_id)

    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_agent=user)
    revision_note = request.POST.get('revision_note', '').strip()

    if not revision_note:
        messages.error(request, 'Revision note is required.')
        return redirect('agent:jw02_review', app_id=app_id)

    jw02 = application.jw02_forms.filter(status='pending_verification').order_by('-uploaded_at').first()
    if jw02:
        jw02.status = 'revision_requested'
        jw02.revision_note = revision_note
        jw02.save()

    change_application_status(application, 'jw02_pending', user, note=f'JW02 revision requested: {revision_note}')

    if application.assigned_hq:
        send_notification(
            application.assigned_hq,
            'JW02 Form Revision Required',
            f'App #{application.app_id}: The JW02 form needs revision. Note: {revision_note}',
            link=f'/hq/revisions/'
        )

    messages.success(request, 'JW02 revision request sent to HQ.')
    return redirect('agent:jw02_review', app_id=app_id)


@role_required('agent', login_url_override='agent:login')
def wallet_page(request):
    """Agent wallet page with balance and transaction history"""
    user = request.user
    wallet = get_or_create_wallet(user)
    transactions = wallet.transactions.all()[:50]
    withdrawal_requests = wallet.withdrawal_requests.all()[:20]

    context = {
        'user': user,
        'wallet': wallet,
        'transactions': transactions,
        'withdrawal_requests': withdrawal_requests,
    }
    return render(request, 'agent/wallet.html', context)


@role_required('agent', login_url_override='agent:login')
def request_withdrawal(request):
    """Agent requests a withdrawal from their wallet"""
    if request.method != 'POST':
        return redirect('agent:wallet')

    user = request.user
    wallet = get_or_create_wallet(user)
    
    try:
        amount = request.POST.get('amount', '0')
        withdrawal = do_request_withdrawal(wallet, amount)
        messages.success(request, f'Withdrawal of ${withdrawal.amount} requested. Pending admin approval.')
    except ValueError as e:
        messages.error(request, str(e))

    return redirect('agent:wallet')


# ——— Agent Notifications ————————————————————————————————————
@role_required('agent', login_url_override='agent:login')
def agent_notifications(request):
    """Display all notifications for the agent"""
    from users.models import Notification
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'agent/notifications.html', {'notifications': notifications})


@role_required('agent', login_url_override='agent:login')
def agent_mark_notification_read(request, notification_id):
    """Mark a single notification as read, then redirect to its link"""
    from users.models import Notification
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    if notification.link:
        return redirect(notification.link)
    return redirect('agent:notifications')


@role_required('agent', login_url_override='agent:login')
def agent_mark_all_read(request):
    """Mark all notifications as read"""
    from users.models import Notification
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('agent:notifications')
