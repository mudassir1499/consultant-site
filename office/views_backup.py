from django.shortcuts import get_object_or_404, render, redirect
from django.db import models
from users.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from scholarships.models import Application, scholarships, ApplicationStatusHistory
from scholarships.utils import change_application_status
from users.notifications import send_notification


def is_office_staff(user):
    return user.is_authenticated and user.role == 'office'


@user_passes_test(is_office_staff, login_url='users:login')
def office_dashboard(request):
    from finance.models import application_payment

    user = request.user

    applications = Application.objects.select_related('user', 'scholarship').all()
    payments = application_payment.objects.select_related('application').all()
    total_payments = sum(payment.amount for payment in payments if payment.payment_status == 'completed')

    context = {
        'user': user,
        'total_applications': applications.count(),
        'submitted_applications': applications.filter(status='submitted').count(),
        'under_review_applications': applications.filter(status='under_review').count(),
        'approved_applications': applications.filter(status='approved').count(),
        'rejected_applications': applications.filter(status='rejected').count(),
        'draft_applications': applications.filter(status='draft').count(),
        'total_payments': total_payments,
        'recent_applications': applications.order_by('-applied_date')[:10],
    }

    return render(request, 'office/dashboard.html', context)


@user_passes_test(is_office_staff, login_url='users:login')
def application_list(request):
    """Display list of scholarship applications"""
    from finance.models import application_payment

    applications = Application.objects.select_related('user', 'scholarship').all()

    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        applications = applications.filter(status=status_filter)

    # Search
    query = request.GET.get('q')
    if query:
        applications = applications.filter(
            models.Q(user__username__icontains=query) |
            models.Q(scholarship__name__icontains=query) |
            models.Q(app_id__icontains=query)
        )

    context = {
        'applications': applications.order_by('-applied_date'),
        'total_applications': Application.objects.count(),
        'submitted_applications': Application.objects.filter(status='submitted').count(),
        'approved_applications': Application.objects.filter(status='approved').count(),
        'rejected_applications': Application.objects.filter(status='rejected').count(),
        'total_payments': application_payment.objects.filter(payment_status='completed').aggregate(total=models.Sum('amount'))['total'] or 0,
    }
    return render(request, 'office/applications.html', context)


@user_passes_test(is_office_staff, login_url='users:login')
def application_detail(request, app_id):
    """Display application details for office staff"""
    from finance.models import application_payment

    application = get_object_or_404(Application.objects.select_related('user', 'scholarship'), app_id=app_id)
    payments = application_payment.objects.filter(application=application)
    status_history = ApplicationStatusHistory.objects.filter(application=application)

    # Get latest admission letter & JW02
    admission_letter = application.admission_letters.first()
    jw02 = application.jw02_forms.first()

    context = {
        'application': application,
        'payments': payments,
        'status_history': status_history,
        'admission_letter': admission_letter,
        'jw02': jw02,
        'documents': {
            'photo': application.photo.url if application.photo else None,
            'graduation_certificate': application.graduation_certificate.url if application.graduation_certificate else None,
            'criminal_record': application.criminal_record.url if application.criminal_record else None,
            'medical_examination': application.medical_examination.url if application.medical_examination else None,
            'letter_of_recommendation_1': application.letter_of_recommendation_1.url if application.letter_of_recommendation_1 else None,
            'letter_of_recommendation_2': application.letter_of_recommendation_2.url if application.letter_of_recommendation_2 else None,
            'study_plan': application.study_plan.url if application.study_plan else None,
            'english_certificate': application.english_certificate.url if application.english_certificate else None,
            'passport': application.passport.url if application.passport else None,
        },
    }
    return render(request, 'office/application-detail.html', context)


@user_passes_test(is_office_staff, login_url='users:login')
def submit_application(request, app_id):
    """Office submits a draft application for agent review"""
    application = get_object_or_404(Application, app_id=app_id)

    if request.method == 'POST' and application.status == 'draft':
        change_application_status(application, 'submitted', request.user, 'Submitted by office worker')
        send_notification(
            application.user,
            'Application Submitted',
            f'Your application #{app_id} for {application.scholarship.name} has been submitted for review.',
            f'/users/dashboard/'
        )
        messages.success(request, f'Application #{app_id} submitted successfully.')

    return redirect('office:application_detail', app_id=app_id)


@user_passes_test(is_office_staff, login_url='users:login')
def payment_list(request):
    """Display list of payments for office staff"""
    from finance.models import application_payment

    payments = application_payment.objects.select_related('application__user', 'application__scholarship').all()
    context = {
        'payments': payments,
    }
    return render(request, 'office/payments.html', context)


@user_passes_test(is_office_staff, login_url='users:login')
def payment_detail(request, payment_id):
    """Display payment details for office staff"""
    from finance.models import application_payment

    payment = get_object_or_404(
        application_payment.objects.select_related('application__user', 'application__scholarship'),
        application_payment_id=payment_id
    )

    context = {
        'payment': payment,
    }
    return render(request, 'office/payment-detail.html', context)


@user_passes_test(is_office_staff, login_url='users:login')
def user_list(request):
    """Display list of users for office staff"""
    users = User.objects.filter(role__in=['user', 'admin']).all()
    context = {
        'users': users,
    }
    return render(request, 'office/users.html', context)


@user_passes_test(is_office_staff, login_url='users:login')
def create_application(request):
    """Allow office staff to create an application for a student"""
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        scholarship_id = request.POST.get('scholarship_id')

        try:
            student = User.objects.get(id=student_id)
            scholarship = scholarships.objects.get(id=scholarship_id)

            application = Application.objects.create(
                user=student,
                scholarship=scholarship,
                status='draft'
            )

            messages.success(request, f'Application created for {student.username}.')
            return redirect('office:application_detail', app_id=application.app_id)

        except (User.DoesNotExist, scholarships.DoesNotExist):
            messages.error(request, 'Invalid student or scholarship selected.')
        except Exception as e:
            messages.error(request, f'Error creating application: {str(e)}')

    students = User.objects.filter(role='user')
    all_scholarships = scholarships.objects.all()

    context = {
        'students': students,
        'scholarships': all_scholarships,
    }
    return render(request, 'office/create_application.html', context)
