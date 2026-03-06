from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Sum, Count, Q
from users.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from scholarships.models import Application, scholarships, ApplicationStatusHistory
from scholarships.utils import change_application_status
from main.utils import validate_uploaded_file
from users.notifications import send_notification
from django.http import JsonResponse
from django.db import transaction

import csv
import logging

from django.views.decorators.http import require_POST

logger = logging.getLogger('office')


def is_office_staff(user):
    return user.is_authenticated and user.role == 'office'


def _get_office(user):
    """Return the Office instance for the current office worker, or None."""
    return getattr(user, 'office', None)


def _office_applications(user):
    """Return an Application queryset scoped to the user's office."""
    office = _get_office(user)
    qs = Application.objects.select_related('user', 'scholarship')
    if office:
        return qs.filter(office=office)
    return qs.none()


def _office_guard(application, user):
    """
    Return True if the application belongs to the user's office.
    If user has no office, always deny.
    """
    office = _get_office(user)
    if not office:
        return False
    return application.office_id == office.pk


# ─── Office Auth ────────────────────────────────────────────────────
def office_login(request):
    """Separate login page for office staff"""
    if request.user.is_authenticated and request.user.role == 'office':
        return redirect('office:office_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not all([username, password]):
            messages.error(request, 'Username and password are required.')
            return render(request, 'office/login.html')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.role != 'office':
                messages.error(request, 'This portal is for office staff only.')
                return render(request, 'office/login.html')
            if user.is_active:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                next_url = request.POST.get('next') or request.GET.get('next')
                return redirect(next_url or 'office:office_dashboard')
            else:
                messages.error(request, 'Your account is inactive.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'office/login.html')


@require_POST
def office_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('office:login')


# ─── Dashboard ──────────────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def office_dashboard(request):
    from finance.models import application_payment

    office = _get_office(request.user)
    applications = _office_applications(request.user)

    status_counts = dict(
        applications.values_list('status').annotate(count=Count('status')).values_list('status', 'count')
    )

    payments_qs = application_payment.objects.filter(application__office=office) if office else application_payment.objects.none()

    total_payments = payments_qs.filter(
        payment_status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0

    pending_payments = payments_qs.filter(
        payment_status__in=['pending', 'under_review']
    ).count()

    context = {
        'user': request.user,
        'office': office,
        'total_applications': applications.count(),
        'submitted_count': status_counts.get('submitted', 0),
        'under_review_count': status_counts.get('under_review', 0),
        'documents_verified_count': status_counts.get('documents_verified', 0),
        'payment_verified_count': status_counts.get('payment_verified', 0),
        'approved_count': status_counts.get('approved', 0),
        'rejected_count': status_counts.get('rejected', 0),
        'draft_count': status_counts.get('draft', 0),
        'complete_count': status_counts.get('complete', 0),
        'total_payments': total_payments,
        'pending_payments': pending_payments,
        'recent_applications': applications.order_by('-applied_date')[:10],
        'needs_action': applications.filter(
            status__in=['submitted', 'under_review', 'documents_verified']
        ).order_by('-applied_date')[:5],
    }

    return render(request, 'office/dashboard.html', context)


# ─── Application List ───────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def application_list(request):
    from finance.models import application_payment
    from django.core.paginator import Paginator

    office = _get_office(request.user)
    applications = _office_applications(request.user)

    status_filter = request.GET.get('status')
    if status_filter:
        applications = applications.filter(status=status_filter)

    query = request.GET.get('q')
    if query:
        applications = applications.filter(
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(scholarship__name__icontains=query) |
            Q(app_id__icontains=query)
        )

    # Date range filter
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        applications = applications.filter(applied_date__gte=date_from)
    if date_to:
        applications = applications.filter(applied_date__lte=date_to)

    applications = applications.order_by('-applied_date')
    paginator = Paginator(applications, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # AJAX: return partial HTML
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'office/_application_table.html', {
            'applications': page_obj,
        })

    office_apps = Application.objects.filter(office=office) if office else Application.objects.none()
    payments_qs = application_payment.objects.filter(application__office=office) if office else application_payment.objects.none()

    context = {
        'applications': page_obj,
        'status_filter': status_filter or '',
        'search_query': query or '',
        'date_from': date_from or '',
        'date_to': date_to or '',
        'status_choices': Application.STATUS_CHOICES,
        'total_applications': office_apps.count(),
        'submitted_count': office_apps.filter(status='submitted').count(),
        'approved_count': office_apps.filter(status='approved').count(),
        'rejected_count': office_apps.filter(status='rejected').count(),
        'total_payments': payments_qs.filter(
            payment_status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0,
    }
    return render(request, 'office/applications.html', context)


# ─── Application Detail ─────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def application_detail(request, app_id):
    from finance.models import application_payment

    office = _get_office(request.user)
    application = get_object_or_404(
        Application.objects.select_related('user', 'scholarship', 'assigned_agent', 'assigned_hq'),
        app_id=app_id, office=office,
    )
    payments = application_payment.objects.filter(application=application)
    status_history = ApplicationStatusHistory.objects.filter(application=application)

    admission_letter = application.admission_letters.first()
    jw02 = application.jw02_forms.first()

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

    can_start_review = application.status == 'submitted'
    can_verify_docs = application.status == 'under_review'
    can_verify_payment = application.status == 'documents_verified'
    can_submit = application.status == 'draft'
    can_forward_to_agent = application.status == 'payment_verified' and not application.assigned_agent

    # Get available agents for forwarding (same office only)
    agents = User.objects.filter(role='agent', is_active=True, office=office) if can_forward_to_agent and office else []

    context = {
        'application': application,
        'payments': payments,
        'status_history': status_history,
        'admission_letter': admission_letter,
        'jw02': jw02,
        'documents': documents,
        'can_start_review': can_start_review,
        'can_verify_docs': can_verify_docs,
        'can_verify_payment': can_verify_payment,
        'can_submit': can_submit,
        'can_forward_to_agent': can_forward_to_agent,
        'agents': agents,
    }
    return render(request, 'office/application-detail.html', context)


# ─── Forward to Agent ────────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def forward_to_agent(request, app_id):
    """Assign a payment_verified application to an agent for approval"""
    office = _get_office(request.user)
    application = get_object_or_404(Application, app_id=app_id, office=office)
    if request.method == 'POST' and application.status == 'payment_verified':
        agent_id = request.POST.get('agent_id')
        if not agent_id:
            messages.error(request, 'Please select an agent.')
            return redirect('office:application_detail', app_id=app_id)

        try:
            agent = User.objects.get(id=agent_id, role='agent', is_active=True, office=office)
        except User.DoesNotExist:
            messages.error(request, 'Invalid agent selected.')
            return redirect('office:application_detail', app_id=app_id)

        application.assigned_agent = agent
        application.save()
        # Log the assignment without changing status (already payment_verified)
        ApplicationStatusHistory.objects.create(
            application=application,
            old_status=application.status,
            new_status=application.status,
            changed_by=request.user,
            note=f'Forwarded to agent {agent.username}',
        )

        # Notify the agent
        send_notification(
            agent, 'New Application Assigned',
            f'Application #{app_id} for {application.scholarship.name} ({application.user.get_full_name() or application.user.username}) has been forwarded to you for review.',
            f'/agent/applications/{app_id}/'
        )
        # Notify the student
        send_notification(
            application.user, 'Application Forwarded',
            f'Your application #{app_id} for {application.scholarship.name} has been forwarded to an agent for approval.',
            f'/scholarships/application/{app_id}/'
        )
        messages.success(request, f'Application #{app_id} forwarded to agent {agent.get_full_name() or agent.username}.')
    return redirect('office:application_detail', app_id=app_id)


# ─── Upload Documents ────────────────────────────────────────────────
DOCUMENT_FIELDS = {
    'passport': 'Passport',
    'photo': 'Photo',
    'graduation_certificate': 'Graduation Certificate',
    'criminal_record': 'Criminal Record',
    'medical_examination': 'Medical Examination',
    'letter_of_recommendation_1': 'Recommendation Letter 1',
    'letter_of_recommendation_2': 'Recommendation Letter 2',
    'study_plan': 'Study Plan',
    'english_certificate': 'English Certificate',
}


@user_passes_test(is_office_staff, login_url='office:login')
def upload_documents(request, app_id):
    """Upload or replace documents for an application"""
    office = _get_office(request.user)
    application = get_object_or_404(
        Application.objects.select_related('user', 'scholarship'),
        app_id=app_id, office=office,
    )

    if request.method == 'POST':
        uploaded_count = 0
        for field_name, label in DOCUMENT_FIELDS.items():
            file = request.FILES.get(field_name)
            if file:
                is_valid, error = validate_uploaded_file(file)
                if not is_valid:
                    messages.error(request, error)
                    return redirect('office:upload_documents', app_id=app_id)
                setattr(application, field_name, file)
                uploaded_count += 1
        if uploaded_count > 0:
            application.save()
            messages.success(request, f'{uploaded_count} document(s) uploaded for application #{app_id}.')
        else:
            messages.warning(request, 'No files were selected.')
        return redirect('office:application_detail', app_id=app_id)

    # Build document info for template
    doc_info = []
    for field_name, label in DOCUMENT_FIELDS.items():
        current_file = getattr(application, field_name)
        doc_info.append({
            'field_name': field_name,
            'label': label,
            'current_file': current_file,
        })

    context = {
        'application': application,
        'doc_info': doc_info,
    }
    return render(request, 'office/upload-documents.html', context)


# ─── Status Transition Actions ──────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def submit_application(request, app_id):
    """Submit a draft application"""
    office = _get_office(request.user)
    application = get_object_or_404(Application, app_id=app_id, office=office)
    if request.method == 'POST' and application.status == 'draft':
        change_application_status(application, 'submitted', request.user, 'Submitted by office worker')
        send_notification(
            application.user, 'Application Submitted',
            f'Your application #{app_id} for {application.scholarship.name} has been submitted for review.',
            '/users/dashboard/'
        )
        messages.success(request, f'Application #{app_id} submitted successfully.')
    return redirect('office:application_detail', app_id=app_id)


@user_passes_test(is_office_staff, login_url='office:login')
def start_review(request, app_id):
    """Move submitted → under_review"""
    office = _get_office(request.user)
    application = get_object_or_404(Application, app_id=app_id, office=office)
    if request.method == 'POST' and application.status == 'submitted':
        change_application_status(application, 'under_review', request.user, 'Review started by office')
        send_notification(
            application.user, 'Application Under Review',
            f'Your application #{app_id} for {application.scholarship.name} is now under review.',
            f'/scholarships/application/{app_id}/'
        )
        messages.success(request, f'Application #{app_id} is now under review.')
    return redirect('office:application_detail', app_id=app_id)


@user_passes_test(is_office_staff, login_url='office:login')
def verify_documents(request, app_id):
    """Move under_review → documents_verified"""
    office = _get_office(request.user)
    application = get_object_or_404(Application, app_id=app_id, office=office)
    if request.method == 'POST' and application.status == 'under_review':
        change_application_status(application, 'documents_verified', request.user, 'Documents verified by office')
        send_notification(
            application.user, 'Documents Verified',
            f'All documents for application #{app_id} have been verified.',
            f'/scholarships/application/{app_id}/'
        )
        messages.success(request, f'Documents for application #{app_id} verified.')
    return redirect('office:application_detail', app_id=app_id)


@user_passes_test(is_office_staff, login_url='office:login')
def verify_payment(request, app_id):
    """Move documents_verified → payment_verified (only if receipt exists)"""
    from finance.models import application_payment as PaymentModel
    office = _get_office(request.user)
    application = get_object_or_404(Application, app_id=app_id, office=office)
    if request.method == 'POST' and application.status == 'documents_verified':
        payment = PaymentModel.objects.filter(application=application).first()
        if not payment or not payment.receipt_pdf:
            messages.error(request, 'Cannot verify payment — no payment receipt has been uploaded.')
            return redirect('office:application_detail', app_id=app_id)
        change_application_status(application, 'payment_verified', request.user, 'Payment verified by office')
        send_notification(
            application.user, 'Payment Verified',
            f'Payment for application #{app_id} has been verified.',
            f'/scholarships/application/{app_id}/'
        )
        messages.success(request, f'Payment for application #{app_id} verified.')
    return redirect('office:application_detail', app_id=app_id)


# ─── Payments ────────────────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def payment_list(request):
    from finance.models import application_payment
    from django.core.paginator import Paginator

    office = _get_office(request.user)
    status_filter = request.GET.get('status', '')
    payments = application_payment.objects.select_related(
        'application__user', 'application__scholarship'
    ).filter(application__office=office).order_by('-payment_date') if office else application_payment.objects.none()

    if status_filter:
        payments = payments.filter(payment_status=status_filter)

    # Date range filter
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)

    # Search
    query = request.GET.get('q', '').strip()
    if query:
        payments = payments.filter(
            Q(application__user__username__icontains=query) |
            Q(application__user__first_name__icontains=query) |
            Q(application__user__last_name__icontains=query) |
            Q(application__scholarship__name__icontains=query) |
            Q(application__app_id__icontains=query)
        )

    paginator = Paginator(payments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # AJAX: return partial HTML
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'office/_payment_table.html', {
            'payments': page_obj,
        })

    context = {
        'payments': page_obj,
        'status_filter': status_filter,
        'search_query': query,
        'date_from': date_from or '',
        'date_to': date_to or '',
    }
    return render(request, 'office/payments.html', context)


@user_passes_test(is_office_staff, login_url='office:login')
def payment_detail(request, payment_id):
    from finance.models import application_payment

    office = _get_office(request.user)
    payment = get_object_or_404(
        application_payment.objects.select_related(
            'application__user', 'application__scholarship', 'reviewed_by'
        ),
        application_payment_id=payment_id, application__office=office,
    )
    can_review = payment.payment_status in ('pending', 'under_review', 'processing')
    context = {
        'payment': payment,
        'can_review': can_review,
    }
    return render(request, 'office/payment-detail.html', context)


# ─── Make Payment (Office uploads receipt for an application) ────────
@user_passes_test(is_office_staff, login_url='office:login')
def make_payment(request, app_id):
    from finance.models import application_payment

    office = _get_office(request.user)
    application = get_object_or_404(
        Application.objects.select_related('user', 'scholarship'),
        app_id=app_id, office=office,
    )

    if request.method == 'POST':
        amount = request.POST.get('amount', '').strip()
        receipt = request.FILES.get('receipt_pdf')
        transaction_id = request.POST.get('transaction_id', '').strip()

        if not amount or not receipt:
            messages.error(request, 'Amount and receipt file are required.')
            return render(request, 'office/make-payment.html', {'application': application})

        is_valid, error = validate_uploaded_file(receipt)
        if not is_valid:
            messages.error(request, error)
            return render(request, 'office/make-payment.html', {'application': application})

        try:
            from decimal import Decimal
            payment = application_payment.objects.create(
                application=application,
                amount=Decimal(amount),
                receipt_pdf=receipt,
                transaction_id=transaction_id or None,
                payment_status='under_review',
            )
            messages.success(request, f'Payment of ${amount} recorded for application #{app_id}.')
            return redirect('office:payment_detail', payment_id=payment.application_payment_id)
        except Exception as e:
            messages.error(request, f'Error creating payment: {str(e)}')

    return render(request, 'office/make-payment.html', {'application': application})


# ─── Approve / Reject Payment ───────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def approve_payment(request, payment_id):
    from finance.models import application_payment
    from django.utils import timezone

    office = _get_office(request.user)
    payment = get_object_or_404(application_payment, application_payment_id=payment_id, application__office=office)
    if request.method == 'POST' and payment.payment_status in ('pending', 'under_review', 'processing'):
        note = request.POST.get('review_note', '').strip()
        payment.payment_status = 'completed'
        payment.reviewed_by = request.user
        payment.reviewed_at = timezone.now()
        payment.review_note = note or 'Approved by office'
        payment.save()
        send_notification(
            payment.application.user, 'Payment Approved',
            f'Your payment of ${payment.amount} for application #{payment.application.app_id} has been approved.',
            f'/scholarships/application/{payment.application.app_id}/'
        )
        messages.success(request, f'Payment #{payment_id} approved.')
    return redirect('office:payment_detail', payment_id=payment_id)


@user_passes_test(is_office_staff, login_url='office:login')
def reject_payment(request, payment_id):
    from finance.models import application_payment
    from django.utils import timezone

    office = _get_office(request.user)
    payment = get_object_or_404(application_payment, application_payment_id=payment_id, application__office=office)
    if request.method == 'POST' and payment.payment_status in ('pending', 'under_review', 'processing'):
        note = request.POST.get('review_note', '').strip()
        payment.payment_status = 'failed'
        payment.reviewed_by = request.user
        payment.reviewed_at = timezone.now()
        payment.review_note = note or 'Rejected by office'
        payment.save()
        send_notification(
            payment.application.user, 'Payment Rejected',
            f'Your payment of ${payment.amount} for application #{payment.application.app_id} has been rejected. Reason: {payment.review_note}',
            f'/scholarships/application/{payment.application.app_id}/'
        )
        messages.success(request, f'Payment #{payment_id} rejected.')
    return redirect('office:payment_detail', payment_id=payment_id)


# ─── Users ───────────────────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def user_list(request):
    """Only show student users belonging to this office"""
    from django.core.paginator import Paginator
    office = _get_office(request.user)
    users = User.objects.filter(role='user', office=office).order_by('-date_joined') if office else User.objects.none()

    query = request.GET.get('q', '').strip()
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'users': page_obj,
        'search_query': query,
        'total_students': User.objects.filter(role='user', office=office).count() if office else 0,
        'active_students': User.objects.filter(role='user', office=office, is_active=True).count() if office else 0,
    }
    return render(request, 'office/users.html', context)


# ─── Create Application ─────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def create_application(request):
    office = _get_office(request.user)
    if not office:
        messages.error(request, 'You are not assigned to any office. Please contact an administrator.')
        return redirect('office:office_dashboard')

    if request.method == 'POST':
        scholarship_id = request.POST.get('scholarship_id')
        student_mode = request.POST.get('student_mode', 'existing')  # 'existing' or 'new'

        try:
            scholarship = scholarships.objects.get(id=scholarship_id)
        except scholarships.DoesNotExist:
            messages.error(request, 'Invalid scholarship selected.')
            return redirect('office:create_application')

        if student_mode == 'new':
            # Create a new student account
            username = request.POST.get('new_username', '').strip()
            email = request.POST.get('new_email', '').strip()
            first_name = request.POST.get('new_first_name', '').strip()
            last_name = request.POST.get('new_last_name', '').strip()
            phone = request.POST.get('new_phone', '').strip()
            new_country = request.POST.get('new_country', '').strip()
            new_city = request.POST.get('new_city', '').strip()

            if not username or not email:
                messages.error(request, 'Username and email are required for new student.')
                return redirect('office:create_application')

            if User.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" is already taken.')
                return redirect('office:create_application')

            if User.objects.filter(email=email).exists():
                messages.error(request, f'Email "{email}" is already registered.')
                return redirect('office:create_application')

            try:
                # Use default password 'password123'
                temp_password = 'password123'
                student = User.objects.create_user(
                    username=username, email=email, password=temp_password,
                    role='user', first_name=first_name, last_name=last_name, phone=phone,
                    office=office, country=new_country, city=new_city,
                )
                application = Application.objects.create(
                    user=student, scholarship=scholarship, status='draft', office=office,
                )

                # Send welcome email with password reset link
                from django.contrib.auth.tokens import default_token_generator
                from django.utils.http import urlsafe_base64_encode
                from django.utils.encoding import force_bytes
                from django.core.mail import send_mail
                from django.conf import settings

                uid = urlsafe_base64_encode(force_bytes(student.pk))
                token = default_token_generator.make_token(student)
                reset_url = f"{request.scheme}://{request.get_host()}/users/password-reset-confirm/{uid}/{token}/"

                try:
                    send_mail(
                        subject='EDU System - Your Student Account Has Been Created',
                        message=(
                            f"Hello {student.get_full_name() or student.username},\n\n"
                            f"An account has been created for you on the EDU System.\n\n"
                            f"Your login credentials:\n"
                            f"  Username: {username}\n"
                            f"  Temporary Password: {temp_password}\n\n"
                            f"Please reset your password using the link below:\n"
                            f"{reset_url}\n\n"
                            f"Thanks,\nEDU System Team"
                        ),
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@edu-system.com'),
                        recipient_list=[email],
                        fail_silently=True,
                    )
                except Exception:
                    pass  # Email failure should not block account creation

                messages.success(
                    request,
                    f'Student account "{username}" created (password: {temp_password}). '
                    f'A password reset email has been sent to {email}.'
                )
                return redirect('office:application_detail', app_id=application.app_id)
            except Exception as e:
                messages.error(request, f'Error creating student: {str(e)}')
                return redirect('office:create_application')
        else:
            # Existing student
            student_id = request.POST.get('student_id')
            try:
                student = User.objects.get(id=student_id, role='user')
                application = Application.objects.create(
                    user=student, scholarship=scholarship, status='draft', office=office,
                )
                # Also associate student with this office if not yet assigned
                if not student.office:
                    student.office = office
                    student.save(update_fields=['office'])
                messages.success(request, f'Application created for {student.username}.')
                return redirect('office:application_detail', app_id=application.app_id)
            except User.DoesNotExist:
                messages.error(request, 'Invalid student selected.')
            except Exception as e:
                messages.error(request, f'Error creating application: {str(e)}')

    context = {
        'students': User.objects.filter(role='user', office=office),
        'scholarships': scholarships.objects.all(),
        'office': office,
    }
    return render(request, 'office/create_application.html', context)


# ─── Notifications ───────────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def office_notifications(request):
    """Display all notifications for the office user"""
    from users.models import Notification
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'office/notifications.html', {'notifications': notifications})


@user_passes_test(is_office_staff, login_url='office:login')
def office_mark_notification_read(request, notification_id):
    """Mark a single notification as read, then redirect to its link"""
    from users.models import Notification
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    if notification.link:
        return redirect(notification.link)
    return redirect('office:notifications')


@user_passes_test(is_office_staff, login_url='office:login')
def office_mark_all_read(request):
    """Mark all notifications as read"""
    from users.models import Notification
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('office:notifications')


# ─── Bulk Actions ────────────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
@require_POST
def bulk_action(request):
    """Handle bulk actions on applications via AJAX JSON"""
    import json
    office = _get_office(request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': 0, 'failed': 0, 'message': 'Invalid request data.'}, status=400)

    action = data.get('action')
    app_ids = data.get('app_ids', [])

    if not action or not app_ids:
        return JsonResponse({'success': 0, 'failed': 0, 'message': 'Missing action or app_ids.'}, status=400)

    VALID_ACTIONS = {
        'start_review': ('submitted', 'under_review', 'Review started by office (bulk)'),
        'verify_documents': ('under_review', 'documents_verified', 'Documents verified by office (bulk)'),
        'verify_payment': ('documents_verified', 'payment_verified', 'Payment verified by office (bulk)'),
    }

    if action == 'forward_to_agent':
        return _bulk_forward_to_agent(request, office, app_ids, data)

    if action not in VALID_ACTIONS:
        return JsonResponse({'success': 0, 'failed': 0, 'message': f'Invalid action: {action}'}, status=400)

    required_status, new_status, note = VALID_ACTIONS[action]
    success = 0
    failed = 0
    errors = []

    apps = Application.objects.filter(app_id__in=app_ids, office=office)
    for app in apps:
        if app.status != required_status:
            failed += 1
            errors.append(f'App #{app.app_id}: wrong status ({app.get_status_display()})')
            continue

        # For verify_payment, check receipt exists
        if action == 'verify_payment':
            from finance.models import application_payment as PaymentModel
            payment = PaymentModel.objects.filter(application=app).first()
            if not payment or not payment.receipt_pdf:
                failed += 1
                errors.append(f'App #{app.app_id}: no payment receipt uploaded')
                continue

        change_application_status(app, new_status, request.user, note)
        success += 1

        # Notification map
        NOTIF = {
            'start_review': ('Application Under Review', 'is now under review.'),
            'verify_documents': ('Documents Verified', 'documents have been verified.'),
            'verify_payment': ('Payment Verified', 'payment has been verified.'),
        }
        title, msg_suffix = NOTIF.get(action, ('Status Updated', 'status has been updated.'))
        send_notification(
            app.user, title,
            f'Your application #{app.app_id} for {app.scholarship.name} {msg_suffix}',
            f'/scholarships/application/{app.app_id}/'
        )

    logger.info(f'Bulk {action}: {success} success, {failed} failed by {request.user.username}')
    return JsonResponse({
        'success': success,
        'failed': failed,
        'errors': errors,
        'message': f'{success} application(s) processed successfully.' + (f' {failed} failed.' if failed else ''),
    })


def _bulk_forward_to_agent(request, office, app_ids, data):
    """Handle bulk forward-to-agent action"""
    agent_id = data.get('agent_id')
    if not agent_id:
        return JsonResponse({'success': 0, 'failed': 0, 'message': 'Please select an agent.'}, status=400)

    try:
        agent = User.objects.get(id=agent_id, role='agent', is_active=True, office=office)
    except User.DoesNotExist:
        return JsonResponse({'success': 0, 'failed': 0, 'message': 'Invalid agent selected.'}, status=400)

    success = 0
    failed = 0
    errors = []

    apps = Application.objects.filter(app_id__in=app_ids, office=office)
    for app in apps:
        if app.status != 'payment_verified':
            failed += 1
            errors.append(f'App #{app.app_id}: wrong status ({app.get_status_display()})')
            continue

        app.assigned_agent = agent
        app.save()
        ApplicationStatusHistory.objects.create(
            application=app, old_status=app.status, new_status=app.status,
            changed_by=request.user, note=f'Bulk forwarded to agent {agent.username}',
        )
        send_notification(
            agent, 'New Application Assigned',
            f'Application #{app.app_id} for {app.scholarship.name} has been forwarded to you.',
            f'/agent/applications/{app.app_id}/'
        )
        send_notification(
            app.user, 'Application Forwarded',
            f'Your application #{app.app_id} has been forwarded to an agent for approval.',
            f'/scholarships/application/{app.app_id}/'
        )
        success += 1

    logger.info(f'Bulk forward_to_agent ({agent.username}): {success} success, {failed} failed by {request.user.username}')
    return JsonResponse({
        'success': success, 'failed': failed, 'errors': errors,
        'message': f'{success} application(s) forwarded to {agent.get_full_name() or agent.username}.',
    })


# ─── Bulk Payment Actions ───────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
@require_POST
def bulk_payment_action(request):
    """Handle bulk approve/reject payments via AJAX JSON"""
    import json
    from finance.models import application_payment
    from django.utils import timezone

    office = _get_office(request.user)

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
        application_payment_id__in=payment_ids, application__office=office
    ).select_related('application__user', 'application__scholarship')

    for payment in payments:
        if payment.payment_status not in reviewable_statuses:
            failed += 1
            errors.append(f'Payment #{payment.application_payment_id}: already {payment.payment_status}')
            continue

        if action == 'approve':
            payment.payment_status = 'completed'
            payment.review_note = 'Approved by office (bulk)'
            notif_msg = f'Your payment of ${payment.amount} for application #{payment.application.app_id} has been approved.'
        else:
            payment.payment_status = 'failed'
            payment.review_note = data.get('reason', 'Rejected by office (bulk)')
            notif_msg = f'Your payment of ${payment.amount} for application #{payment.application.app_id} has been rejected.'

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

    logger.info(f'Bulk payment {action}: {success} success, {failed} failed by {request.user.username}')
    return JsonResponse({
        'success': success, 'failed': failed, 'errors': errors,
        'message': f'{success} payment(s) {action}d successfully.',
    })


# ─── CSV Export ──────────────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def export_applications_csv(request):
    """Export filtered applications as CSV"""
    import csv
    from django.http import HttpResponse

    office = _get_office(request.user)
    applications = _office_applications(request.user)

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
    applications = applications.order_by('-applied_date')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="applications_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['App ID', 'Applicant', 'Email', 'Scholarship', 'Status', 'Applied Date', 'Agent', 'HQ'])
    for app in applications:
        writer.writerow([
            app.app_id,
            app.user.get_full_name() or app.user.username,
            app.user.email,
            app.scholarship.name,
            app.get_status_display(),
            app.applied_date.strftime('%Y-%m-%d') if app.applied_date else '',
            app.assigned_agent.username if app.assigned_agent else '-',
            app.assigned_hq.username if app.assigned_hq else '-',
        ])

    logger.info(f'CSV export: {applications.count()} applications by {request.user.username}')
    return response


@user_passes_test(is_office_staff, login_url='office:login')
def export_payments_csv(request):
    """Export filtered payments as CSV"""
    import csv
    from django.http import HttpResponse
    from finance.models import application_payment

    office = _get_office(request.user)
    payments = application_payment.objects.select_related(
        'application__user', 'application__scholarship'
    ).filter(application__office=office).order_by('-payment_date') if office else application_payment.objects.none()

    status_filter = request.GET.get('status')
    if status_filter:
        payments = payments.filter(payment_status=status_filter)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="payments_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Payment ID', 'Student', 'Scholarship', 'Amount', 'Status', 'Date', 'App ID'])
    for p in payments:
        writer.writerow([
            p.application_payment_id,
            p.application.user.get_full_name() or p.application.user.username,
            p.application.scholarship.name,
            str(p.amount),
            p.get_payment_status_display(),
            p.payment_date.strftime('%Y-%m-%d') if p.payment_date else '',
            p.application.app_id,
        ])

    return response
