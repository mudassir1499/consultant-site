"""
Admin Portal Views — Superuser dashboard for full operations management.
Provides unified access to all applications, documents, payments, users, and withdrawals.
"""
import csv
import io
import json
import logging
import zipfile
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from finance.models import Wallet, WithdrawalRequest, application_payment, bank_account
from finance.services import approve_withdrawal, reject_withdrawal
from main.utils import validate_uploaded_file
from office.models import Office, OfficeRegion
from pages.models import SiteSettings
from scholarships.models import (
    AdmissionLetter, Application, ApplicationStatusHistory, JW02Form, scholarships,
)
from scholarships.utils import change_application_status
from users.models import User
from users.notifications import send_notification

logger = logging.getLogger('admin_portal')


def is_superuser(user):
    return user.is_authenticated and user.is_superuser


# ═══════════════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════════════
@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_dashboard(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    today = now.date()

    # Application stats
    total_apps = Application.objects.count()
    apps_today = Application.objects.filter(applied_date__date=today).count()
    apps_this_week = Application.objects.filter(applied_date__gte=week_ago).count()

    status_counts = dict(
        Application.objects.values_list('status')
        .annotate(c=Count('status'))
        .values_list('status', 'c')
    )

    # User stats
    total_users = User.objects.count()
    users_by_role = dict(
        User.objects.values_list('role')
        .annotate(c=Count('role'))
        .values_list('role', 'c')
    )

    # Payment stats
    total_payments = application_payment.objects.count()
    payment_status_counts = dict(
        application_payment.objects.values_list('payment_status')
        .annotate(c=Count('payment_status'))
        .values_list('payment_status', 'c')
    )
    total_revenue = application_payment.objects.filter(
        payment_status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Withdrawal stats
    pending_withdrawals = WithdrawalRequest.objects.filter(status='pending').count()
    total_withdrawals = WithdrawalRequest.objects.filter(
        status='approved'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Recent applications
    recent_applications = Application.objects.select_related(
        'user', 'scholarship', 'office', 'assigned_agent', 'assigned_hq'
    ).order_by('-applied_date')[:10]

    # Pending actions
    pending_reviews = Application.objects.filter(status='submitted').count()
    pending_payments = Application.objects.filter(status='documents_verified').count()
    pending_letters = Application.objects.filter(status='admission_letter_uploaded').count()
    pending_jw02s = Application.objects.filter(status='jw02_uploaded').count()

    # Scholarship count
    total_scholarships = scholarships.objects.count()

    context = {
        'total_apps': total_apps,
        'apps_today': apps_today,
        'apps_this_week': apps_this_week,
        'status_counts': status_counts,
        'status_choices': Application.STATUS_CHOICES,
        'total_users': total_users,
        'users_by_role': users_by_role,
        'total_payments': total_payments,
        'payment_status_counts': payment_status_counts,
        'total_revenue': total_revenue,
        'pending_withdrawals': pending_withdrawals,
        'total_withdrawals': total_withdrawals,
        'recent_applications': recent_applications,
        'total_scholarships': total_scholarships,
        'pending_reviews': pending_reviews,
        'pending_payments': pending_payments,
        'pending_letters': pending_letters,
        'pending_jw02s': pending_jw02s,
    }
    return render(request, 'admin_portal/dashboard.html', context)


# ═══════════════════════════════════════════════════════════════════════
# Applications
# ═══════════════════════════════════════════════════════════════════════
@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_application_list(request):
    applications = Application.objects.select_related(
        'user', 'scholarship', 'office', 'assigned_agent', 'assigned_hq'
    ).order_by('-applied_date')

    # Filters
    status_filter = request.GET.get('status', '')
    office_filter = request.GET.get('office', '')
    query = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if status_filter:
        applications = applications.filter(status=status_filter)
    if office_filter:
        applications = applications.filter(office_id=office_filter)
    if query:
        applications = applications.filter(
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(scholarship__name__icontains=query) |
            Q(app_id__icontains=query)
        )
    if date_from:
        applications = applications.filter(applied_date__gte=date_from)
    if date_to:
        applications = applications.filter(applied_date__lte=date_to)

    paginator = Paginator(applications, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    offices = Office.objects.filter(is_active=True)

    context = {
        'applications': page_obj,
        'status_filter': status_filter,
        'office_filter': office_filter,
        'search_query': query,
        'date_from': date_from or '',
        'date_to': date_to or '',
        'status_choices': Application.STATUS_CHOICES,
        'offices': offices,
    }
    return render(request, 'admin_portal/application_list.html', context)


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_application_detail(request, app_id):
    application = get_object_or_404(
        Application.objects.select_related(
            'user', 'scholarship', 'office', 'assigned_agent', 'assigned_hq'
        ),
        app_id=app_id
    )

    payments = application_payment.objects.filter(application=application)
    status_history = ApplicationStatusHistory.objects.filter(application=application).order_by('-changed_at')
    admission_letters = application.admission_letters.all()
    jw02_forms = application.jw02_forms.all()

    documents = {
        'Passport': application.passport,
        'Photo': application.photo,
        'Graduation Certificate': application.graduation_certificate,
        'Criminal Record': application.criminal_record,
        'Medical Examination': application.medical_examination,
        'Recommendation Letter 1': application.letter_of_recommendation_1,
        'Recommendation Letter 2': application.letter_of_recommendation_2,
        'Study Plan': application.study_plan,
        'English Certificate': application.english_certificate,
    }

    # Available agents for assignment
    available_agents = User.objects.filter(role='agent', is_active=True)
    available_hq = User.objects.filter(role='headquarters', status='active')

    context = {
        'application': application,
        'payments': payments,
        'status_history': status_history,
        'documents': documents,
        'admission_letters': admission_letters,
        'jw02_forms': jw02_forms,
        'available_agents': available_agents,
        'available_hq': available_hq,
    }
    return render(request, 'admin_portal/application_detail.html', context)


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_download_documents(request, app_id):
    """Download all application documents as a ZIP file."""
    application = get_object_or_404(Application, app_id=app_id)

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
    logger.info(f'Admin {request.user.username} downloaded documents for App #{app_id}')
    return response


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_verify_documents(request, app_id):
    """Admin marks documents as verified."""
    application = get_object_or_404(Application, app_id=app_id)
    if application.status == 'under_review':
        change_application_status(application, 'documents_verified', request.user, 'Documents verified by admin')
        send_notification(
            application.user, 'Documents Verified',
            f'All documents for application #{app_id} have been verified by admin.',
            f'/scholarships/application/{app_id}/'
        )
        messages.success(request, f'Documents for application #{app_id} verified.')
    else:
        messages.error(request, 'Application must be under review to verify documents.')
    return redirect('admin_portal:application_detail', app_id=app_id)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_verify_payment(request, app_id):
    """Admin verifies payment and moves to payment_verified."""
    application = get_object_or_404(Application, app_id=app_id)
    if application.status == 'documents_verified':
        payment = application_payment.objects.filter(application=application).first()
        if not payment or not payment.receipt_pdf:
            messages.error(request, 'No payment receipt found for this application.')
            return redirect('admin_portal:application_detail', app_id=app_id)
        
        payment.payment_status = 'completed'
        payment.reviewed_by = request.user
        payment.reviewed_at = timezone.now()
        payment.review_note = 'Verified by admin'
        payment.save()
        
        change_application_status(application, 'payment_verified', request.user, 'Payment verified by admin')
        send_notification(
            application.user, 'Payment Verified',
            f'Payment for application #{app_id} has been verified by admin.',
            f'/scholarships/application/{app_id}/'
        )
        messages.success(request, f'Payment for application #{app_id} verified.')
    else:
        messages.error(request, 'Application must have documents verified to verify payment.')
    return redirect('admin_portal:application_detail', app_id=app_id)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_approve_application(request, app_id):
    """Admin approves application and assigns to HQ."""
    application = get_object_or_404(Application, app_id=app_id)
    if application.status in ('submitted', 'under_review', 'documents_verified', 'payment_verified'):
        from datetime import timedelta
        deadline_days = int(request.POST.get('deadline_days', 10))
        application.deadline = timezone.now() + timedelta(days=deadline_days)
        
        # Assign HQ if provided
        hq_id = request.POST.get('assigned_hq')
        if hq_id:
            try:
                hq_user = User.objects.get(id=hq_id, role='headquarters')
                application.assigned_hq = hq_user
            except User.DoesNotExist:
                pass
        
        change_application_status(application, 'approved', request.user, 'Approved by admin')
        application.save()
        
        send_notification(
            application.user, 'Application Approved',
            f'Your application #{app_id} has been approved by admin.',
            f'/scholarships/application/{app_id}/'
        )
        if application.assigned_hq:
            send_notification(
                application.assigned_hq, 'New Application Assigned',
                f'Application #{app_id} has been assigned to you by admin.',
                f'/hq/applications/{app_id}/'
            )
        messages.success(request, f'Application #{app_id} approved.')
    else:
        messages.error(request, 'Application cannot be approved from current status.')
    return redirect('admin_portal:application_detail', app_id=app_id)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_reject_application(request, app_id):
    """Admin rejects application with reason."""
    application = get_object_or_404(Application, app_id=app_id)
    rejection_reason = request.POST.get('rejection_reason', '').strip()
    if not rejection_reason:
        messages.error(request, 'Rejection reason is required.')
        return redirect('admin_portal:application_detail', app_id=app_id)
    
    application.rejection_reason = rejection_reason
    change_application_status(application, 'rejected', request.user, f'Rejected by admin: {rejection_reason}')
    send_notification(
        application.user, 'Application Rejected',
        f'Your application #{app_id} has been rejected. Reason: {rejection_reason}',
        f'/scholarships/application/{app_id}/'
    )
    messages.success(request, f'Application #{app_id} rejected.')
    return redirect('admin_portal:application_detail', app_id=app_id)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_upload_admission_letter(request, app_id):
    """Admin uploads admission letter for an application."""
    application = get_object_or_404(Application, app_id=app_id)
    file = request.FILES.get('admission_letter')
    if not file:
        messages.error(request, 'Please select a file to upload.')
        return redirect('admin_portal:application_detail', app_id=app_id)
    
    is_valid, error = validate_uploaded_file(file)
    if not is_valid:
        messages.error(request, error)
        return redirect('admin_portal:application_detail', app_id=app_id)
    
    AdmissionLetter.objects.create(
        application=application,
        uploaded_by=request.user,
        file=file,
        status='pending_verification',
    )
    
    change_application_status(application, 'admission_letter_uploaded', request.user, 'Admission letter uploaded by admin')
    
    if application.assigned_agent:
        send_notification(
            application.assigned_agent, 'Admission Letter Uploaded',
            f'Admin has uploaded an admission letter for App #{app_id}. Please review.',
            f'/agent/admission-letter/{app_id}/'
        )
    
    messages.success(request, 'Admission letter uploaded successfully.')
    return redirect('admin_portal:application_detail', app_id=app_id)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_upload_jw02(request, app_id):
    """Admin uploads JW02 form for an application."""
    application = get_object_or_404(Application, app_id=app_id)
    file = request.FILES.get('jw02_form')
    if not file:
        messages.error(request, 'Please select a file to upload.')
        return redirect('admin_portal:application_detail', app_id=app_id)
    
    is_valid, error = validate_uploaded_file(file)
    if not is_valid:
        messages.error(request, error)
        return redirect('admin_portal:application_detail', app_id=app_id)
    
    JW02Form.objects.create(
        application=application,
        uploaded_by=request.user,
        file=file,
        status='pending_verification',
    )
    
    change_application_status(application, 'jw02_uploaded', request.user, 'JW02 form uploaded by admin')
    
    if application.assigned_agent:
        send_notification(
            application.assigned_agent, 'JW02 Form Uploaded',
            f'Admin has uploaded the JW02 form for App #{app_id}. Please review.',
            f'/agent/jw02/{app_id}/'
        )
    
    messages.success(request, 'JW02 form uploaded successfully.')
    return redirect('admin_portal:application_detail', app_id=app_id)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_reupload_letter(request, app_id, letter_id):
    """Admin re-uploads a corrected admission letter."""
    application = get_object_or_404(Application, app_id=app_id)
    old_letter = get_object_or_404(AdmissionLetter, id=letter_id, application=application)
    
    file = request.FILES.get('admission_letter')
    if not file:
        messages.error(request, 'Please select a file.')
        return redirect('admin_portal:application_detail', app_id=app_id)
    
    is_valid, error = validate_uploaded_file(file)
    if not is_valid:
        messages.error(request, error)
        return redirect('admin_portal:application_detail', app_id=app_id)
    
    AdmissionLetter.objects.create(
        application=application,
        uploaded_by=request.user,
        file=file,
        status='pending_verification',
    )
    
    change_application_status(application, 'admission_letter_uploaded', request.user, 'Revised admission letter uploaded by admin')
    
    if application.assigned_agent:
        send_notification(
            application.assigned_agent, 'Revised Admission Letter Uploaded',
            f'Admin has re-uploaded the admission letter for App #{app_id}. Please review.',
            f'/agent/admission-letter/{app_id}/'
        )
    
    messages.success(request, 'Revised admission letter uploaded.')
    return redirect('admin_portal:application_detail', app_id=app_id)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_reupload_jw02(request, app_id, jw02_id):
    """Admin re-uploads a corrected JW02 form."""
    application = get_object_or_404(Application, app_id=app_id)
    old_jw02 = get_object_or_404(JW02Form, id=jw02_id, application=application)
    
    file = request.FILES.get('jw02_form')
    if not file:
        messages.error(request, 'Please select a file.')
        return redirect('admin_portal:application_detail', app_id=app_id)
    
    is_valid, error = validate_uploaded_file(file)
    if not is_valid:
        messages.error(request, error)
        return redirect('admin_portal:application_detail', app_id=app_id)
    
    JW02Form.objects.create(
        application=application,
        uploaded_by=request.user,
        file=file,
        status='pending_verification',
    )
    
    change_application_status(application, 'jw02_uploaded', request.user, 'Revised JW02 form uploaded by admin')
    
    if application.assigned_agent:
        send_notification(
            application.assigned_agent, 'Revised JW02 Form Uploaded',
            f'Admin has re-uploaded the JW02 form for App #{app_id}. Please review.',
            f'/agent/jw02/{app_id}/'
        )
    
    messages.success(request, 'Revised JW02 form uploaded.')
    return redirect('admin_portal:application_detail', app_id=app_id)


# ═══════════════════════════════════════════════════════════════════════
# Payments
# ═══════════════════════════════════════════════════════════════════════
@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_payment_list(request):
    payments = application_payment.objects.select_related(
        'application__user', 'application__scholarship', 'application__office', 'reviewed_by'
    ).order_by('-payment_date')

    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if status_filter:
        payments = payments.filter(payment_status=status_filter)
    if query:
        payments = payments.filter(
            Q(application__user__username__icontains=query) |
            Q(application__user__first_name__icontains=query) |
            Q(application__user__last_name__icontains=query) |
            Q(application__scholarship__name__icontains=query) |
            Q(transaction_id__icontains=query)
        )
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)

    paginator = Paginator(payments, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'payments': page_obj,
        'status_filter': status_filter,
        'search_query': query,
        'date_from': date_from or '',
        'date_to': date_to or '',
    }
    return render(request, 'admin_portal/payment_list.html', context)


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_payment_detail(request, payment_id):
    payment = get_object_or_404(
        application_payment.objects.select_related(
            'application__user', 'application__scholarship', 'reviewed_by'
        ),
        application_payment_id=payment_id
    )
    can_review = payment.payment_status in ('pending', 'under_review', 'processing')
    context = {'payment': payment, 'can_review': can_review}
    return render(request, 'admin_portal/payment_detail.html', context)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_approve_payment(request, payment_id):
    payment = get_object_or_404(application_payment, application_payment_id=payment_id)
    if payment.payment_status in ('pending', 'under_review', 'processing'):
        note = request.POST.get('review_note', '').strip()
        payment.payment_status = 'completed'
        payment.reviewed_by = request.user
        payment.reviewed_at = timezone.now()
        payment.review_note = note or 'Approved by admin'
        payment.save()
        
        send_notification(
            payment.application.user, 'Payment Approved',
            f'Your payment of ${payment.amount} for application #{payment.application.app_id} has been approved by admin.',
            f'/scholarships/application/{payment.application.app_id}/'
        )
        messages.success(request, f'Payment #{payment_id} approved.')
    else:
        messages.error(request, 'Payment cannot be approved.')
    return redirect('admin_portal:payment_detail', payment_id=payment_id)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_reject_payment(request, payment_id):
    payment = get_object_or_404(application_payment, application_payment_id=payment_id)
    if payment.payment_status in ('pending', 'under_review', 'processing'):
        note = request.POST.get('review_note', '').strip()
        payment.payment_status = 'failed'
        payment.reviewed_by = request.user
        payment.reviewed_at = timezone.now()
        payment.review_note = note or 'Rejected by admin'
        payment.save()
        
        send_notification(
            payment.application.user, 'Payment Rejected',
            f'Your payment of ${payment.amount} for application #{payment.application.app_id} has been rejected by admin.',
            f'/scholarships/application/{payment.application.app_id}/'
        )
        messages.success(request, f'Payment #{payment_id} rejected.')
    else:
        messages.error(request, 'Payment cannot be rejected.')
    return redirect('admin_portal:payment_detail', payment_id=payment_id)


# ═══════════════════════════════════════════════════════════════════════
# Users
# ═══════════════════════════════════════════════════════════════════════
@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_student_list(request):
    students = User.objects.filter(role='user').order_by('-date_joined')
    query = request.GET.get('q', '').strip()
    if query:
        students = students.filter(
            Q(username__icontains=query) | Q(first_name__icontains=query) |
            Q(last_name__icontains=query) | Q(email__icontains=query)
        )
    paginator = Paginator(students, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_portal/student_list.html', {'students': page_obj, 'search_query': query})


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_office_list(request):
    offices = Office.objects.all().order_by('name')
    return render(request, 'admin_portal/office_list.html', {'offices': offices})


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_agent_list(request):
    agents = User.objects.filter(role='agent').order_by('-date_joined')
    query = request.GET.get('q', '').strip()
    if query:
        agents = agents.filter(
            Q(username__icontains=query) | Q(first_name__icontains=query) |
            Q(last_name__icontains=query) | Q(email__icontains=query)
        )
    paginator = Paginator(agents, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_portal/agent_list.html', {'agents': page_obj, 'search_query': query})


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_hq_list(request):
    hq_users = User.objects.filter(role='headquarters').order_by('-date_joined')
    query = request.GET.get('q', '').strip()
    if query:
        hq_users = hq_users.filter(
            Q(username__icontains=query) | Q(first_name__icontains=query) |
            Q(last_name__icontains=query) | Q(email__icontains=query)
        )
    paginator = Paginator(hq_users, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_portal/hq_list.html', {'hq_users': page_obj, 'search_query': query})


# ═══════════════════════════════════════════════════════════════════════
# Withdrawals
# ═══════════════════════════════════════════════════════════════════════
@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_withdrawal_list(request):
    withdrawals = WithdrawalRequest.objects.select_related(
        'wallet__user'
    ).order_by('-requested_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        withdrawals = withdrawals.filter(status=status_filter)

    paginator = Paginator(withdrawals, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'withdrawals': page_obj,
        'status_filter': status_filter,
        'pending_count': WithdrawalRequest.objects.filter(status='pending').count(),
    }
    return render(request, 'admin_portal/withdrawal_list.html', context)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_approve_withdrawal(request, withdrawal_id):
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    try:
        approve_withdrawal(withdrawal, request.user)
        send_notification(
            withdrawal.wallet.user, 'Withdrawal Approved',
            f'Your withdrawal request of ${withdrawal.amount} has been approved by admin.',
            '/agent/wallet/' if withdrawal.wallet.user.role == 'agent' else '/hq/wallet/'
        )
        messages.success(request, f'Withdrawal #{withdrawal_id} approved.')
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('admin_portal:withdrawal_list')


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_reject_withdrawal(request, withdrawal_id):
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    reason = request.POST.get('reason', '').strip()
    try:
        reject_withdrawal(withdrawal, request.user, reason)
        send_notification(
            withdrawal.wallet.user, 'Withdrawal Rejected',
            f'Your withdrawal request of ${withdrawal.amount} has been rejected by admin. Reason: {reason}',
            '/agent/wallet/' if withdrawal.wallet.user.role == 'agent' else '/hq/wallet/'
        )
        messages.success(request, f'Withdrawal #{withdrawal_id} rejected.')
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('admin_portal:withdrawal_list')


# ═══════════════════════════════════════════════════════════════════════
# Bulk Actions
# ═══════════════════════════════════════════════════════════════════════
@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_bulk_action(request):
    """Handle bulk actions on applications via AJAX JSON."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': 0, 'failed': 0, 'message': 'Invalid request data.'}, status=400)

    action = data.get('action')
    app_ids = data.get('app_ids', [])

    if not action or not app_ids:
        return JsonResponse({'success': 0, 'failed': 0, 'message': 'Missing action or app_ids.'}, status=400)

    VALID_ACTIONS = {
        'verify_documents': ('under_review', 'documents_verified', 'Documents verified by admin (bulk)'),
        'verify_payment': ('documents_verified', 'payment_verified', 'Payment verified by admin (bulk)'),
        'approve': ('payment_verified', 'approved', 'Approved by admin (bulk)'),
    }

    if action not in VALID_ACTIONS:
        return JsonResponse({'success': 0, 'failed': 0, 'message': f'Invalid action: {action}'}, status=400)

    required_status, new_status, note = VALID_ACTIONS[action]
    success = 0
    failed = 0
    errors = []

    apps = Application.objects.filter(app_id__in=app_ids)
    for app in apps:
        if app.status != required_status:
            failed += 1
            errors.append(f'App #{app.app_id}: wrong status ({app.get_status_display()})')
            continue

        # For verify_payment, check receipt exists
        if action == 'verify_payment':
            payment = application_payment.objects.filter(application=app).first()
            if not payment or not payment.receipt_pdf:
                failed += 1
                errors.append(f'App #{app.app_id}: no payment receipt uploaded')
                continue

        change_application_status(app, new_status, request.user, note)
        success += 1

        NOTIF = {
            'verify_documents': ('Documents Verified', 'documents have been verified by admin.'),
            'verify_payment': ('Payment Verified', 'payment has been verified by admin.'),
            'approve': ('Application Approved', 'has been approved by admin.'),
        }
        title, msg_suffix = NOTIF.get(action, ('Status Updated', 'status has been updated.'))
        send_notification(
            app.user, title,
            f'Your application #{app.app_id} for {app.scholarship.name} {msg_suffix}',
            f'/scholarships/application/{app.app_id}/'
        )

    logger.info(f'Admin {request.user.username} bulk {action}: {success} success, {failed} failed')
    return JsonResponse({
        'success': success,
        'failed': failed,
        'errors': errors,
        'message': f'{success} application(s) processed successfully.' + (f' {failed} failed.' if failed else ''),
    })


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_bulk_payment_action(request):
    """Handle bulk approve/reject payments via AJAX JSON."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': 0, 'failed': 0, 'message': 'Invalid request data.'}, status=400)

    action = data.get('action')
    payment_ids = data.get('payment_ids', [])

    if action not in ('approve', 'reject') or not payment_ids:
        return JsonResponse({'success': 0, 'failed': 0, 'message': 'Invalid action or payment_ids.'}, status=400)

    success = 0
    failed = 0
    errors = []
    reviewable_statuses = ('pending', 'under_review', 'processing')

    payments = application_payment.objects.filter(
        application_payment_id__in=payment_ids
    ).select_related('application__user', 'application__scholarship')

    for payment in payments:
        if payment.payment_status not in reviewable_statuses:
            failed += 1
            errors.append(f'Payment #{payment.application_payment_id}: already {payment.payment_status}')
            continue

        if action == 'approve':
            payment.payment_status = 'completed'
            payment.review_note = 'Approved by admin (bulk)'
            notif_msg = f'Your payment of ${payment.amount} for application #{payment.application.app_id} has been approved by admin.'
        else:
            payment.payment_status = 'failed'
            payment.review_note = data.get('reason', 'Rejected by admin (bulk)')
            notif_msg = f'Your payment of ${payment.amount} for application #{payment.application.app_id} has been rejected by admin.'

        payment.reviewed_by = request.user
        payment.reviewed_at = timezone.now()
        payment.save()
        send_notification(
            payment.application.user,
            'Payment Approved' if action == 'approve' else 'Payment Rejected',
            notif_msg,
            f'/scholarships/application/{payment.application.app_id}/'
        )
        success += 1

    logger.info(f'Admin {request.user.username} bulk payment {action}: {success} success, {failed} failed')
    return JsonResponse({
        'success': success, 'failed': failed, 'errors': errors,
        'message': f'{success} payment(s) {action}d successfully.',
    })


# ═══════════════════════════════════════════════════════════════════════
# CSV Exports
# ═══════════════════════════════════════════════════════════════════════
@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_export_applications_csv(request):
    applications = Application.objects.select_related('user', 'scholarship', 'office').order_by('-applied_date')

    status_filter = request.GET.get('status')
    if status_filter:
        applications = applications.filter(status=status_filter)
    query = request.GET.get('q')
    if query:
        applications = applications.filter(
            Q(user__username__icontains=query) | Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) | Q(scholarship__name__icontains=query) |
            Q(app_id__icontains=query)
        )
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        applications = applications.filter(applied_date__gte=date_from)
    if date_to:
        applications = applications.filter(applied_date__lte=date_to)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="admin_applications_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['App ID', 'Applicant', 'Email', 'Scholarship', 'Office', 'Status', 'Applied Date', 'Agent', 'HQ', 'Payment Status'])
    for app in applications:
        payment = application_payment.objects.filter(application=app).first()
        writer.writerow([
            app.app_id,
            app.user.get_full_name() or app.user.username,
            app.user.email,
            app.scholarship.name,
            app.office.name if app.office else '-',
            app.get_status_display(),
            app.applied_date.strftime('%Y-%m-%d') if app.applied_date else '',
            app.assigned_agent.username if app.assigned_agent else '-',
            app.assigned_hq.username if app.assigned_hq else '-',
            payment.payment_status if payment else '-',
        ])
    logger.info(f'Admin {request.user.username} exported {applications.count()} applications to CSV')
    return response


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_export_payments_csv(request):
    payments = application_payment.objects.select_related('application__user', 'application__scholarship').order_by('-payment_date')

    status_filter = request.GET.get('status')
    if status_filter:
        payments = payments.filter(payment_status=status_filter)
    query = request.GET.get('q')
    if query:
        payments = payments.filter(
            Q(application__user__username__icontains=query) |
            Q(application__scholarship__name__icontains=query) |
            Q(transaction_id__icontains=query)
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="admin_payments_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Payment ID', 'App ID', 'Student', 'Email', 'Scholarship', 'Amount', 'Status', 'Date', 'Transaction ID', 'Reviewed By'])
    for payment in payments:
        writer.writerow([
            payment.application_payment_id,
            payment.application.app_id,
            payment.application.user.get_full_name() or payment.application.user.username,
            payment.application.user.email,
            payment.application.scholarship.name,
            str(payment.amount),
            payment.get_payment_status_display(),
            payment.payment_date.strftime('%Y-%m-%d') if payment.payment_date else '',
            payment.transaction_id or '-',
            payment.reviewed_by.username if payment.reviewed_by else '-',
        ])
    logger.info(f'Admin {request.user.username} exported {payments.count()} payments to CSV')
    return response


# ═══════════════════════════════════════════════════════════════════════
# Scholarships
# ═══════════════════════════════════════════════════════════════════════
@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_scholarship_list(request):
    """List all scholarships with application counts."""
    scholarships_qs = scholarships.objects.annotate(
        app_count=Count('application'),
        completed_count=Count('application', filter=Q(application__status='complete'))
    ).order_by('-deadline')

    query = request.GET.get('q', '').strip()
    degree_filter = request.GET.get('degree', '')
    type_filter = request.GET.get('type', '')
    if query:
        scholarships_qs = scholarships_qs.filter(
            Q(name__icontains=query) | Q(city__icontains=query) | Q(major__icontains=query)
        )
    if degree_filter:
        scholarships_qs = scholarships_qs.filter(degree=degree_filter)
    if type_filter:
        scholarships_qs = scholarships_qs.filter(scholarship_type=type_filter)

    paginator = Paginator(scholarships_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'scholarships': page_obj,
        'search_query': query,
        'degree_filter': degree_filter,
        'type_filter': type_filter,
        'degree_choices': scholarships.DEGREE_CHOICES,
        'type_choices': scholarships.SCHOLARSHIP_TYPE_CHOICES,
    }
    return render(request, 'admin_portal/scholarship_list.html', context)


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_scholarship_create(request):
    """Create a new scholarship."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        city = request.POST.get('city', '').strip()
        major = request.POST.get('major', '').strip()
        degree = request.POST.get('degree', '')
        language = request.POST.get('language', '').strip()
        scholarship_type = request.POST.get('scholarship_type', '')
        deadline = request.POST.get('deadline', '')
        semester = request.POST.get('semester', '')
        price = request.POST.get('price', '0')
        eligibility = request.POST.get('eligibility', '').strip()
        note = request.POST.get('note', '').strip()
        agent_commission = request.POST.get('agent_commission', '0')
        hq_commission = request.POST.get('hq_commission', '0')

        if not all([name, description, city, major, degree, language, scholarship_type, deadline, semester]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'admin_portal/scholarship_form.html', {
                'degree_choices': scholarships.DEGREE_CHOICES,
                'type_choices': scholarships.SCHOLARSHIP_TYPE_CHOICES,
                'semester_choices': scholarships.SEMESTER_CHOICES,
            })

        try:
            from decimal import Decimal
            scholarship = scholarships.objects.create(
                name=name,
                description=description,
                city=city,
                major=major,
                degree=degree,
                language=language,
                scholarship_type=scholarship_type,
                deadline=deadline,
                semester=semester,
                price=Decimal(price),
                eligibility=eligibility,
                note=note or None,
                agent_commission=Decimal(agent_commission) if agent_commission else Decimal('0'),
                hq_commission=Decimal(hq_commission) if hq_commission else Decimal('0'),
            )
            messages.success(request, f'Scholarship "{scholarship.name}" created successfully.')
            return redirect('admin_portal:scholarship_list')
        except Exception as e:
            messages.error(request, f'Error creating scholarship: {str(e)}')

    context = {
        'degree_choices': scholarships.DEGREE_CHOICES,
        'type_choices': scholarships.SCHOLARSHIP_TYPE_CHOICES,
        'semester_choices': scholarships.SEMESTER_CHOICES,
        'is_create': True,
    }
    return render(request, 'admin_portal/scholarship_form.html', context)


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_scholarship_detail(request, scholarship_id):
    """View scholarship details with applications."""
    scholarship = get_object_or_404(
        scholarships.objects.annotate(
            app_count=Count('application'),
            completed_count=Count('application', filter=Q(application__status='complete'))
        ),
        id=scholarship_id
    )

    applications = Application.objects.filter(scholarship=scholarship).select_related(
        'user', 'office', 'assigned_agent', 'assigned_hq'
    ).order_by('-applied_date')[:20]

    context = {
        'scholarship': scholarship,
        'applications': applications,
    }
    return render(request, 'admin_portal/scholarship_detail.html', context)


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_scholarship_edit(request, scholarship_id):
    """Edit an existing scholarship."""
    scholarship = get_object_or_404(scholarships, id=scholarship_id)

    if request.method == 'POST':
        scholarship.name = request.POST.get('name', '').strip()
        scholarship.description = request.POST.get('description', '').strip()
        scholarship.city = request.POST.get('city', '').strip()
        scholarship.major = request.POST.get('major', '').strip()
        scholarship.degree = request.POST.get('degree', '')
        scholarship.language = request.POST.get('language', '').strip()
        scholarship.scholarship_type = request.POST.get('scholarship_type', '')
        scholarship.deadline = request.POST.get('deadline', '')
        scholarship.semester = request.POST.get('semester', '')
        scholarship.price = request.POST.get('price', '0')
        scholarship.eligibility = request.POST.get('eligibility', '').strip()
        scholarship.note = request.POST.get('note', '').strip() or None
        scholarship.agent_commission = request.POST.get('agent_commission', '0')
        scholarship.hq_commission = request.POST.get('hq_commission', '0')

        try:
            scholarship.save()
            messages.success(request, f'Scholarship "{scholarship.name}" updated successfully.')
            return redirect('admin_portal:scholarship_list')
        except Exception as e:
            messages.error(request, f'Error updating scholarship: {str(e)}')

    context = {
        'scholarship': scholarship,
        'degree_choices': scholarships.DEGREE_CHOICES,
        'type_choices': scholarships.SCHOLARSHIP_TYPE_CHOICES,
        'semester_choices': scholarships.SEMESTER_CHOICES,
        'is_create': False,
    }
    return render(request, 'admin_portal/scholarship_form.html', context)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_scholarship_delete(request, scholarship_id):
    """Delete a scholarship."""
    scholarship = get_object_or_404(scholarships, id=scholarship_id)
    name = scholarship.name
    scholarship.delete()
    messages.success(request, f'Scholarship "{name}" deleted successfully.')
    return redirect('admin_portal:scholarship_list')


# ═══════════════════════════════════════════════════════════════════════
# User Management (create / edit / status / password / delete)
# ═══════════════════════════════════════════════════════════════════════
ROLE_REDIRECT = {
    'user': 'admin_portal:student_list',
    'office': 'admin_portal:office_list',
    'agent': 'admin_portal:agent_list',
    'headquarters': 'admin_portal:hq_list',
}


def _user_form_context(target, is_create, **extra):
    ctx = {
        'target': target,
        'is_create': is_create,
        'role_choices': User._meta.get_field('role').choices,
        'status_choices': User.STATUS_CHOICES,
        'offices': Office.objects.filter(is_active=True).order_by('name'),
    }
    ctx.update(extra)
    return ctx


def _user_from_post(request, instance):
    """Bind editable fields from POST onto a (possibly unsaved) User instance."""
    instance.email = request.POST.get('email', '').strip()
    instance.first_name = request.POST.get('first_name', '').strip()
    instance.last_name = request.POST.get('last_name', '').strip()
    instance.phone = request.POST.get('phone', '').strip()
    instance.role = request.POST.get('role', instance.role or 'user')
    instance.status = request.POST.get('status', instance.status or 'active')
    instance.city = request.POST.get('city', '').strip()
    instance.country = request.POST.get('country', '').strip()
    office_id = request.POST.get('office') or None
    instance.office = Office.objects.filter(pk=office_id).first() if office_id else None
    return instance


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_user_create(request):
    """Create a user of any role. Role can be pre-filled via ?role=agent."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        draft = _user_from_post(request, User())
        draft.username = username

        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return render(request, 'admin_portal/user_form.html', _user_form_context(draft, True))
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" is already taken.')
            return render(request, 'admin_portal/user_form.html', _user_form_context(draft, True))

        draft.is_staff = draft.role == 'user' and request.POST.get('is_staff') == 'on'
        draft.set_password(password)
        draft.save()

        logger.info(f'Admin {request.user.username} created {draft.role} user "{username}"')
        messages.success(request, f'{draft.get_role_display()} "{username}" created successfully.')
        return redirect(ROLE_REDIRECT.get(draft.role, 'admin_portal:student_list'))

    draft = User(role=request.GET.get('role', 'user'), status='active')
    return render(request, 'admin_portal/user_form.html', _user_form_context(draft, True))


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_user_edit(request, user_id):
    """Edit an existing user."""
    target = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        _user_from_post(request, target)
        target.save()

        logger.info(f'Admin {request.user.username} edited user "{target.username}"')
        messages.success(request, f'User "{target.username}" updated successfully.')
        return redirect(ROLE_REDIRECT.get(target.role, 'admin_portal:student_list'))

    return render(request, 'admin_portal/user_form.html', _user_form_context(target, False))


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_user_toggle_status(request, user_id):
    """Activate / suspend a user account."""
    target = get_object_or_404(User, id=user_id)
    if target.id == request.user.id:
        messages.error(request, 'You cannot change the status of your own account.')
    else:
        target.status = 'suspended' if target.status == 'active' else 'active'
        target.save()
        messages.success(request, f'User "{target.username}" is now {target.get_status_display()}.')
    return redirect(ROLE_REDIRECT.get(target.role, 'admin_portal:student_list'))


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_user_reset_password(request, user_id):
    """Set a new password for a user."""
    target = get_object_or_404(User, id=user_id)
    new_password = request.POST.get('new_password', '')
    if len(new_password) < 8:
        messages.error(request, 'Password must be at least 8 characters.')
    else:
        target.set_password(new_password)
        target.save()
        logger.info(f'Admin {request.user.username} reset password for "{target.username}"')
        messages.success(request, f'Password for "{target.username}" has been reset.')
    return redirect('admin_portal:user_edit', user_id=user_id)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_user_delete(request, user_id):
    """Delete a user account."""
    target = get_object_or_404(User, id=user_id)
    if target.id == request.user.id:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('admin_portal:user_edit', user_id=user_id)
    if target.is_superuser:
        messages.error(request, 'Superuser accounts cannot be deleted from here.')
        return redirect('admin_portal:user_edit', user_id=user_id)

    role, username = target.role, target.username
    target.delete()
    logger.info(f'Admin {request.user.username} deleted user "{username}"')
    messages.success(request, f'User "{username}" deleted.')
    return redirect(ROLE_REDIRECT.get(role, 'admin_portal:student_list'))


# ═══════════════════════════════════════════════════════════════════════
# Office & Region Management
# ═══════════════════════════════════════════════════════════════════════
def _apply_office_fields(office, request):
    office.name = request.POST.get('name', '').strip()
    office.code = request.POST.get('code', '').strip()
    office.city = request.POST.get('city', '').strip()
    office.country = request.POST.get('country', '').strip()
    office.address = request.POST.get('address', '').strip()
    office.phone = request.POST.get('phone', '').strip()
    office.email = request.POST.get('email', '').strip()
    office.is_default = request.POST.get('is_default') == 'on'
    office.is_active = request.POST.get('is_active') == 'on'
    return office


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_office_create(request):
    if request.method == 'POST':
        office = _apply_office_fields(Office(), request)
        if not office.name or not office.code:
            messages.error(request, 'Name and code are required.')
            return render(request, 'admin_portal/office_form.html', {'is_create': True, 'office': office})
        if Office.objects.filter(code=office.code).exists():
            messages.error(request, f'Office code "{office.code}" already exists.')
            return render(request, 'admin_portal/office_form.html', {'is_create': True, 'office': office})
        office.save()
        messages.success(request, f'Office "{office.name}" created.')
        return redirect('admin_portal:office_edit', office_id=office.id)

    return render(request, 'admin_portal/office_form.html', {'is_create': True, 'office': Office()})


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_office_edit(request, office_id):
    office = get_object_or_404(Office, id=office_id)
    if request.method == 'POST':
        _apply_office_fields(office, request)
        try:
            office.save()
            messages.success(request, f'Office "{office.name}" updated.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('admin_portal:office_edit', office_id=office.id)

    context = {
        'is_create': False,
        'office': office,
        'regions': office.regions.all(),
        'staff': office.staff.all(),
    }
    return render(request, 'admin_portal/office_form.html', context)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_office_delete(request, office_id):
    office = get_object_or_404(Office, id=office_id)
    name = office.name
    office.delete()
    messages.success(request, f'Office "{name}" deleted.')
    return redirect('admin_portal:office_list')


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_office_region_add(request, office_id):
    office = get_object_or_404(Office, id=office_id)
    country_code = request.POST.get('country_code', '').strip().upper()
    country_name = request.POST.get('country_name', '').strip()
    city = request.POST.get('city', '').strip()
    if not country_code or not country_name:
        messages.error(request, 'Country code and name are required.')
        return redirect('admin_portal:office_edit', office_id=office_id)
    if OfficeRegion.objects.filter(country_code=country_code, city=city).exists():
        messages.error(request, 'A routing rule for this country/city already exists.')
        return redirect('admin_portal:office_edit', office_id=office_id)
    OfficeRegion.objects.create(
        office=office, country_code=country_code, country_name=country_name, city=city,
    )
    messages.success(request, 'Routing rule added.')
    return redirect('admin_portal:office_edit', office_id=office_id)


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_office_region_delete(request, region_id):
    region = get_object_or_404(OfficeRegion, id=region_id)
    office_id = region.office_id
    region.delete()
    messages.success(request, 'Routing rule removed.')
    return redirect('admin_portal:office_edit', office_id=office_id)


# ═══════════════════════════════════════════════════════════════════════
# Bank Account Management
# ═══════════════════════════════════════════════════════════════════════
@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_bank_list(request):
    accounts = bank_account.objects.all().order_by('-created_at')
    return render(request, 'admin_portal/bank_list.html', {'accounts': accounts})


def _apply_bank_fields(account, request):
    account.bank_name = request.POST.get('bank_name', '').strip()
    account.account_number = request.POST.get('account_number', '').strip()
    account.account_holder_name = request.POST.get('account_holder_name', '').strip()
    account.iban = request.POST.get('iban', '').strip() or None
    account.swift_code = request.POST.get('swift_code', '').strip()
    account.status = request.POST.get('status', 'active')
    return account


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_bank_create(request):
    if request.method == 'POST':
        account = _apply_bank_fields(bank_account(), request)
        if not account.bank_name or not account.account_number:
            messages.error(request, 'Bank name and account number are required.')
            return render(request, 'admin_portal/bank_form.html', {'is_create': True, 'account': account})
        account.save()
        messages.success(request, f'Bank account "{account.bank_name}" added.')
        return redirect('admin_portal:bank_list')
    return render(request, 'admin_portal/bank_form.html', {'is_create': True, 'account': bank_account()})


@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_bank_edit(request, account_id):
    account = get_object_or_404(bank_account, account_id=account_id)
    if request.method == 'POST':
        _apply_bank_fields(account, request)
        account.save()
        messages.success(request, f'Bank account "{account.bank_name}" updated.')
        return redirect('admin_portal:bank_list')
    return render(request, 'admin_portal/bank_form.html', {'is_create': False, 'account': account})


@user_passes_test(is_superuser, login_url='/admin/login/')
@require_POST
def admin_bank_delete(request, account_id):
    account = get_object_or_404(bank_account, account_id=account_id)
    name = account.bank_name
    account.delete()
    messages.success(request, f'Bank account "{name}" deleted.')
    return redirect('admin_portal:bank_list')


# ═══════════════════════════════════════════════════════════════════════
# Site Settings (singleton)
# ═══════════════════════════════════════════════════════════════════════
@user_passes_test(is_superuser, login_url='/admin/login/')
def admin_site_settings(request):
    settings_obj = SiteSettings.load()

    if request.method == 'POST':
        text_fields = [
            'site_name', 'tagline', 'meta_description', 'meta_keywords',
            'contact_email', 'contact_phone', 'address',
            'facebook_url', 'instagram_url', 'twitter_url', 'linkedin_url',
            'youtube_url', 'whatsapp_number', 'google_analytics_id', 'footer_text',
        ]
        for field in text_fields:
            setattr(settings_obj, field, request.POST.get(field, '').strip())

        for img_field in ('logo', 'favicon', 'og_image'):
            uploaded = request.FILES.get(img_field)
            if uploaded:
                setattr(settings_obj, img_field, uploaded)

        settings_obj.save()
        logger.info(f'Admin {request.user.username} updated site settings')
        messages.success(request, 'Site settings saved successfully.')
        return redirect('admin_portal:site_settings')

    return render(request, 'admin_portal/site_settings.html', {'settings': settings_obj})
