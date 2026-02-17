from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Sum, Count, Q
from users.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from scholarships.models import Application, scholarships, ApplicationStatusHistory
from scholarships.utils import change_application_status
from users.notifications import send_notification


def is_office_staff(user):
    return user.is_authenticated and user.role == 'office'


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
                return redirect('office:office_dashboard')
            else:
                messages.error(request, 'Your account is inactive.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'office/login.html')


def office_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('office:login')


# ─── Dashboard ──────────────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def office_dashboard(request):
    from finance.models import application_payment

    applications = Application.objects.select_related('user', 'scholarship').all()

    status_counts = dict(
        applications.values_list('status').annotate(count=Count('status')).values_list('status', 'count')
    )

    total_payments = application_payment.objects.filter(
        payment_status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0

    pending_payments = application_payment.objects.filter(
        payment_status__in=['pending', 'under_review']
    ).count()

    context = {
        'user': request.user,
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

    applications = Application.objects.select_related('user', 'scholarship').all()

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

    context = {
        'applications': applications.order_by('-applied_date'),
        'status_filter': status_filter or '',
        'search_query': query or '',
        'status_choices': Application.STATUS_CHOICES,
        'total_applications': Application.objects.count(),
        'submitted_count': Application.objects.filter(status='submitted').count(),
        'approved_count': Application.objects.filter(status='approved').count(),
        'rejected_count': Application.objects.filter(status='rejected').count(),
        'total_payments': application_payment.objects.filter(
            payment_status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0,
    }
    return render(request, 'office/applications.html', context)


# ─── Application Detail ─────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def application_detail(request, app_id):
    from finance.models import application_payment

    application = get_object_or_404(
        Application.objects.select_related('user', 'scholarship', 'assigned_agent', 'assigned_hq'),
        app_id=app_id
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

    # Get available agents for forwarding
    agents = User.objects.filter(role='agent', is_active=True) if can_forward_to_agent else []

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
    application = get_object_or_404(Application, app_id=app_id)
    if request.method == 'POST' and application.status == 'payment_verified':
        agent_id = request.POST.get('agent_id')
        if not agent_id:
            messages.error(request, 'Please select an agent.')
            return redirect('office:application_detail', app_id=app_id)

        try:
            agent = User.objects.get(id=agent_id, role='agent', is_active=True)
        except User.DoesNotExist:
            messages.error(request, 'Invalid agent selected.')
            return redirect('office:application_detail', app_id=app_id)

        application.assigned_agent = agent
        application.save()
        change_application_status(application, 'payment_verified', request.user, f'Forwarded to agent {agent.username}')

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
    application = get_object_or_404(
        Application.objects.select_related('user', 'scholarship'),
        app_id=app_id
    )

    if request.method == 'POST':
        uploaded_count = 0
        for field_name, label in DOCUMENT_FIELDS.items():
            file = request.FILES.get(field_name)
            if file:
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
    application = get_object_or_404(Application, app_id=app_id)
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
    application = get_object_or_404(Application, app_id=app_id)
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
    application = get_object_or_404(Application, app_id=app_id)
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
    """Move documents_verified → payment_verified"""
    application = get_object_or_404(Application, app_id=app_id)
    if request.method == 'POST' and application.status == 'documents_verified':
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

    status_filter = request.GET.get('status', '')
    payments = application_payment.objects.select_related(
        'application__user', 'application__scholarship'
    ).all().order_by('-payment_date')

    if status_filter:
        payments = payments.filter(payment_status=status_filter)

    context = {
        'payments': payments,
        'status_filter': status_filter,
    }
    return render(request, 'office/payments.html', context)


@user_passes_test(is_office_staff, login_url='office:login')
def payment_detail(request, payment_id):
    from finance.models import application_payment

    payment = get_object_or_404(
        application_payment.objects.select_related(
            'application__user', 'application__scholarship', 'reviewed_by'
        ),
        application_payment_id=payment_id
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

    application = get_object_or_404(
        Application.objects.select_related('user', 'scholarship'),
        app_id=app_id
    )

    if request.method == 'POST':
        amount = request.POST.get('amount', '').strip()
        receipt = request.FILES.get('receipt_pdf')
        transaction_id = request.POST.get('transaction_id', '').strip()

        if not amount or not receipt:
            messages.error(request, 'Amount and receipt file are required.')
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

    payment = get_object_or_404(application_payment, application_payment_id=payment_id)
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

    payment = get_object_or_404(application_payment, application_payment_id=payment_id)
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
    """Only show student users — hide office, agent, HQ staff"""
    users = User.objects.filter(role='user').order_by('-date_joined')

    query = request.GET.get('q', '').strip()
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    context = {
        'users': users,
        'search_query': query,
        'total_students': User.objects.filter(role='user').count(),
        'active_students': User.objects.filter(role='user', is_active=True).count(),
    }
    return render(request, 'office/users.html', context)


# ─── Create Application ─────────────────────────────────────────────
@user_passes_test(is_office_staff, login_url='office:login')
def create_application(request):
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
                )
                application = Application.objects.create(
                    user=student, scholarship=scholarship, status='draft'
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
                    user=student, scholarship=scholarship, status='draft'
                )
                messages.success(request, f'Application created for {student.username}.')
                return redirect('office:application_detail', app_id=application.app_id)
            except User.DoesNotExist:
                messages.error(request, 'Invalid student selected.')
            except Exception as e:
                messages.error(request, f'Error creating application: {str(e)}')

    context = {
        'students': User.objects.filter(role='user'),
        'scholarships': scholarships.objects.all(),
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
