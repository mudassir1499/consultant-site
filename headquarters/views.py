import io
import zipfile
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta

from users.decorators import role_required
from users.models import User
from users.notifications import send_notification
from scholarships.models import Application, AdmissionLetter, JW02Form
from scholarships.utils import change_application_status
from main.utils import validate_uploaded_file
from finance.services import (
    get_or_create_wallet,
    request_withdrawal as do_request_withdrawal,
)


# â”€â”€â”€ HQ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def hq_login(request):
    """Separate login page for headquarters staff"""
    if request.user.is_authenticated and request.user.role == 'headquarters':
        return redirect('headquarters:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not all([username, password]):
            messages.error(request, 'Username and password are required.')
            return render(request, 'headquarters/login.html')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.role != 'headquarters':
                messages.error(request, 'This portal is for headquarters staff only.')
                return render(request, 'headquarters/login.html')
            if user.is_active:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                next_url = request.POST.get('next') or request.GET.get('next')
                return redirect(next_url or 'headquarters:dashboard')
            else:
                messages.error(request, 'Your account is inactive.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'headquarters/login.html')


@require_POST
def hq_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('headquarters:login')


@role_required('headquarters', login_url_override='headquarters:login')
def dashboard(request):
    """HQ dashboard with assigned applications, wallet summary"""
    user = request.user
    assigned = Application.objects.filter(assigned_hq=user).select_related('user', 'scholarship')
    wallet = get_or_create_wallet(user)

    # Group applications by status for tabs
    approved_apps = assigned.filter(status='approved')
    in_progress_apps = assigned.filter(status='in_progress').select_related('scholarship')
    letter_apps = assigned.filter(status__in=['admission_letter_uploaded', 'admission_letter_approved', 'letter_pending'])
    jw02_apps = assigned.filter(status__in=['jw02_uploaded', 'jw02_approved', 'jw02_pending'])
    completed_apps = assigned.filter(status='complete')
    revision_apps = assigned.filter(status__in=['letter_pending', 'jw02_pending'])

    pending_revisions_count = AdmissionLetter.objects.filter(
        application__assigned_hq=user, status='revision_requested'
    ).count() + JW02Form.objects.filter(
        application__assigned_hq=user, status='revision_requested'
    ).count()

    context = {
        'user': user,
        'wallet': wallet,
        'total_assigned': assigned.count(),
        'in_progress': in_progress_apps.count(),
        'approved_pending': approved_apps.count(),
        'pending_revisions': pending_revisions_count,
        'completed_count': completed_apps.count(),
        'letter_count': letter_apps.count(),
        'jw02_count': jw02_apps.count(),
        'revision_count': revision_apps.count(),
        'in_progress_apps': in_progress_apps,
        'all_applications': assigned.order_by('-applied_date'),
        'approved_apps': approved_apps.order_by('-applied_date'),
        'in_progress_apps_list': in_progress_apps.order_by('-applied_date'),
        'letter_apps': letter_apps.order_by('-applied_date'),
        'jw02_apps': jw02_apps.order_by('-applied_date'),
        'completed_apps': completed_apps.order_by('-applied_date'),
        'revision_apps': revision_apps.order_by('-applied_date'),
    }
    return render(request, 'headquarters/dashboard.html', context)


@role_required('headquarters', login_url_override='headquarters:login')
def application_list(request):
    """List all applications assigned to this HQ user"""
    user = request.user

    all_apps = Application.objects.filter(
        assigned_hq=user
    ).select_related('user', 'scholarship').order_by('-applied_date')

    # Search filter
    from django.db.models import Q
    query = request.GET.get('q', '').strip()
    if query:
        all_apps = all_apps.filter(
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(scholarship__name__icontains=query) |
            Q(app_id__icontains=query)
        )

    approved_apps = all_apps.filter(status='approved')
    in_progress_apps = all_apps.filter(status='in_progress')
    letter_apps = all_apps.filter(status__in=['admission_letter_uploaded', 'admission_letter_approved', 'letter_pending'])
    jw02_apps = all_apps.filter(status__in=['jw02_uploaded', 'jw02_approved', 'jw02_pending'])
    completed_apps = all_apps.filter(status='complete')
    revision_apps = all_apps.filter(status__in=['letter_pending', 'jw02_pending'])

    context = {
        'user': user,
        'all_applications': all_apps,
        'search_query': query,
        'approved_apps': approved_apps,
        'in_progress_apps': in_progress_apps,
        'letter_apps': letter_apps,
        'jw02_apps': jw02_apps,
        'completed_apps': completed_apps,
        'revision_apps': revision_apps,
        'total_count': all_apps.count(),
        'approved_count': approved_apps.count(),
        'progress_count': in_progress_apps.count(),
        'letter_count': letter_apps.count(),
        'jw02_count': jw02_apps.count(),
        'completed_count': completed_apps.count(),
        'revision_count': revision_apps.count(),
    }
    return render(request, 'headquarters/application_list.html', context)


@role_required('headquarters', login_url_override='headquarters:login')
def application_detail(request, app_id):
    """View application details with action buttons for HQ"""
    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_hq=user)
    admission_letters = application.admission_letters.all()
    jw02_forms = application.jw02_forms.all()
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
        'documents': documents,
        'admission_letters': admission_letters,
        'jw02_forms': jw02_forms,
        'status_history': status_history,
    }
    return render(request, 'headquarters/application_detail.html', context)


@role_required('headquarters', login_url_override='headquarters:login')
def download_documents(request, app_id):
    """Download all application documents as a ZIP file"""
    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_hq=user)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        doc_fields = [
            ('passport', application.passport),
            ('photo', application.photo),
            ('graduation_certificate', application.graduation_certificate),
            ('criminal_record', application.criminal_record),
            ('medical_examination', application.medical_examination),
            ('recommendation_letter_1', application.letter_of_recommendation_1),
            ('recommendation_letter_2', application.letter_of_recommendation_2),
            ('study_plan', application.study_plan),
            ('english_certificate', application.english_certificate),
        ]
        for name, field in doc_fields:
            if field and field.name:
                try:
                    ext = field.name.split('.')[-1] if '.' in field.name else 'pdf'
                    zf.writestr(f"{name}.{ext}", field.read())
                except Exception:
                    pass

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="app_{app_id}_documents.zip"'
    return response


@role_required('headquarters', login_url_override='headquarters:login')
def mark_applied(request, app_id):
    """Mark application as applied to university â€” starts deadline"""
    if request.method != 'POST':
        return redirect('headquarters:application_detail', app_id=app_id)

    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_hq=user)

    if application.status != 'approved':
        messages.error(request, 'Application must be in Approved status to mark as applied.')
        return redirect('headquarters:application_detail', app_id=app_id)

    # Set 10-day deadline
    application.deadline = timezone.now() + timedelta(days=10)
    change_application_status(application, 'in_progress', user, note='Applied to university by HQ')

    # Notify agent
    if application.assigned_agent:
        send_notification(
            application.assigned_agent,
            'Application Applied to University',
            f'HQ has applied App #{application.app_id} to the university. Deadline set for admission letter upload.',
            link=f'/agent/applications/{application.app_id}/'
        )

    messages.success(request, f'Application #{app_id} marked as In Progress. Deadline: {application.deadline.strftime("%b %d, %Y")}')
    return redirect('headquarters:application_detail', app_id=app_id)


@role_required('headquarters', login_url_override='headquarters:login')
def upload_admission_letter(request, app_id):
    """Upload admission letter for an application"""
    if request.method != 'POST':
        return redirect('headquarters:application_detail', app_id=app_id)

    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_hq=user)
    file = request.FILES.get('admission_letter')

    if not file:
        messages.error(request, 'Please select a file to upload.')
        return redirect('headquarters:application_detail', app_id=app_id)

    is_valid, error = validate_uploaded_file(file)
    if not is_valid:
        messages.error(request, error)
        return redirect('headquarters:application_detail', app_id=app_id)

    AdmissionLetter.objects.create(
        application=application,
        uploaded_by=user,
        file=file,
        status='pending_verification',
    )

    change_application_status(application, 'admission_letter_uploaded', user, note='Admission letter uploaded by HQ')

    # Notify agent
    if application.assigned_agent:
        send_notification(
            application.assigned_agent,
            'Admission Letter Uploaded',
            f'HQ has uploaded an admission letter for App #{application.app_id} ({application.scholarship.name}). Please review.',
            link=f'/agent/admission-letter/{application.app_id}/'
        )

    messages.success(request, 'Admission letter uploaded and sent for agent verification.')
    return redirect('headquarters:application_detail', app_id=app_id)


@role_required('headquarters', login_url_override='headquarters:login')
def upload_jw02(request, app_id):
    """Upload JW02 form after admission letter is approved"""
    user = request.user
    application = get_object_or_404(Application, app_id=app_id, assigned_hq=user)

    if request.method == 'POST':
        file = request.FILES.get('jw02_form')
        if not file:
            messages.error(request, 'Please select a file to upload.')
            return redirect('headquarters:upload_jw02', app_id=app_id)

        is_valid, error = validate_uploaded_file(file)
        if not is_valid:
            messages.error(request, error)
            return redirect('headquarters:upload_jw02', app_id=app_id)

        JW02Form.objects.create(
            application=application,
            uploaded_by=user,
            file=file,
            status='pending_verification',
        )

        change_application_status(application, 'jw02_uploaded', user, note='JW02 form uploaded by HQ')

        # Notify agent
        if application.assigned_agent:
            send_notification(
                application.assigned_agent,
                'JW02 Form Uploaded',
                f'HQ has uploaded the JW02 form for App #{application.app_id} ({application.scholarship.name}). Please review.',
                link=f'/agent/jw02/{application.app_id}/'
            )

        messages.success(request, 'JW02 form uploaded and sent for agent verification.')
        return redirect('headquarters:application_detail', app_id=app_id)

    context = {
        'user': user,
        'application': application,
    }
    return render(request, 'headquarters/upload_jw02.html', context)


@role_required('headquarters', login_url_override='headquarters:login')
def revision_list(request):
    """List admission letters and JW02 forms that need revision"""
    user = request.user
    letters = AdmissionLetter.objects.filter(
        application__assigned_hq=user,
        status='revision_requested'
    ).select_related('application__user', 'application__scholarship').order_by('-uploaded_at')

    jw02_revisions = JW02Form.objects.filter(
        application__assigned_hq=user,
        status='revision_requested'
    ).select_related('application__user', 'application__scholarship').order_by('-uploaded_at')

    context = {
        'user': user,
        'revisions': letters,
        'jw02_revisions': jw02_revisions,
    }
    return render(request, 'headquarters/revision_list.html', context)


@role_required('headquarters', login_url_override='headquarters:login')
def reupload_letter(request, letter_id):
    """Re-upload a corrected admission letter"""
    user = request.user
    old_letter = get_object_or_404(
        AdmissionLetter,
        id=letter_id,
        application__assigned_hq=user,
        status='revision_requested'
    )

    if request.method == 'POST':
        file = request.FILES.get('admission_letter')
        if not file:
            messages.error(request, 'Please select a file.')
            return redirect('headquarters:revision_list')

        is_valid, error = validate_uploaded_file(file)
        if not is_valid:
            messages.error(request, error)
            return redirect('headquarters:revision_list')

        # Create new letter
        AdmissionLetter.objects.create(
            application=old_letter.application,
            uploaded_by=user,
            file=file,
            status='pending_verification',
        )

        change_application_status(
            old_letter.application, 'admission_letter_uploaded', user,
            note='Revised admission letter uploaded by HQ'
        )

        # Notify agent
        if old_letter.application.assigned_agent:
            send_notification(
                old_letter.application.assigned_agent,
                'Revised Admission Letter Uploaded',
                f'HQ has re-uploaded the admission letter for App #{old_letter.application.app_id}. Please review.',
                link=f'/agent/admission-letter/{old_letter.application.app_id}/'
            )

        messages.success(request, 'Revised admission letter uploaded.')
        return redirect('headquarters:revision_list')

    context = {
        'user': user,
        'letter': old_letter,
    }
    return render(request, 'headquarters/reupload_letter.html', context)


@role_required('headquarters', login_url_override='headquarters:login')
def reupload_jw02(request, jw02_id):
    """Re-upload a corrected JW02 form"""
    user = request.user
    old_jw02 = get_object_or_404(
        JW02Form,
        id=jw02_id,
        application__assigned_hq=user,
        status='revision_requested'
    )

    if request.method == 'POST':
        file = request.FILES.get('jw02_form')
        if not file:
            messages.error(request, 'Please select a file.')
            return redirect('headquarters:revision_list')

        is_valid, error = validate_uploaded_file(file)
        if not is_valid:
            messages.error(request, error)
            return redirect('headquarters:revision_list')

        JW02Form.objects.create(
            application=old_jw02.application,
            uploaded_by=user,
            file=file,
            status='pending_verification',
        )

        change_application_status(
            old_jw02.application, 'jw02_uploaded', user,
            note='Revised JW02 form uploaded by HQ'
        )

        if old_jw02.application.assigned_agent:
            send_notification(
                old_jw02.application.assigned_agent,
                'Revised JW02 Form Uploaded',
                f'HQ has re-uploaded the JW02 form for App #{old_jw02.application.app_id}. Please review.',
                link=f'/agent/jw02/{old_jw02.application.app_id}/'
            )

        messages.success(request, 'Revised JW02 form uploaded.')
        return redirect('headquarters:revision_list')

    context = {
        'user': user,
        'jw02': old_jw02,
    }
    return render(request, 'headquarters/reupload_jw02.html', context)


@role_required('headquarters', login_url_override='headquarters:login')
def wallet_page(request):
    """HQ wallet page with balance and transaction history"""
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
    return render(request, 'headquarters/wallet.html', context)


@role_required('headquarters', login_url_override='headquarters:login')
def request_withdrawal(request):
    """HQ requests a withdrawal from their wallet"""
    if request.method != 'POST':
        return redirect('headquarters:wallet')

    user = request.user
    wallet = get_or_create_wallet(user)

    try:
        amount = request.POST.get('amount', '0')
        withdrawal = do_request_withdrawal(wallet, amount)
        messages.success(request, f'Withdrawal of ${withdrawal.amount} requested. Pending admin approval.')
    except ValueError as e:
        messages.error(request, str(e))

    return redirect('headquarters:wallet')


# ——— HQ Notifications ——————————————————————————————————————
@role_required('headquarters', login_url_override='headquarters:login')
def hq_notifications(request):
    """Display all notifications for the HQ user"""
    from users.models import Notification
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'headquarters/notifications.html', {'notifications': notifications})


@role_required('headquarters', login_url_override='headquarters:login')
def hq_mark_notification_read(request, notification_id):
    """Mark a single notification as read, then redirect to its link"""
    from users.models import Notification
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    if notification.link:
        return redirect(notification.link)
    return redirect('headquarters:notifications')


@role_required('headquarters', login_url_override='headquarters:login')
def hq_mark_all_read(request):
    """Mark all notifications as read"""
    from users.models import Notification
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('headquarters:notifications')
