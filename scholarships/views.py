from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from main.utils import validate_uploaded_file
from .models import scholarships, Application


def scholarship_list(request):
    """Browse all available scholarships"""
    qs = scholarships.objects.all().order_by('-deadline')

    # Filters
    query = request.GET.get('q', '').strip()
    degree = request.GET.get('degree', '')
    scholarship_type = request.GET.get('type', '')

    if query:
        qs = qs.filter(
            Q(name__icontains=query) |
            Q(city__icontains=query) |
            Q(major__icontains=query) |
            Q(description__icontains=query)
        )
    if degree:
        qs = qs.filter(degree=degree)
    if scholarship_type:
        qs = qs.filter(scholarship_type=scholarship_type)

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'scholarships': page_obj,
        'search_query': query,
        'degree_filter': degree,
        'type_filter': scholarship_type,
        'degree_choices': scholarships.DEGREE_CHOICES,
        'type_choices': scholarships.SCHOLARSHIP_TYPE_CHOICES,
    }
    return render(request, 'scholarships/scholarship_list.html', context)


def scholarship_detail(request, scholarship_id):
    """View details of a single scholarship"""
    scholarship = get_object_or_404(scholarships, id=scholarship_id)
    context = {'scholarship': scholarship}
    return render(request, 'scholarships/scholarship_detail.html', context)

@login_required
def apply_scholarship(request, scholarship_id):
    """Handle scholarship application"""
    
    # Get scholarship
    scholarship = get_object_or_404(scholarships, id=scholarship_id)
    user = request.user
    
    # Check if already applied (excluding drafts if you want to allow multiple drafts? Let's check existing non-drafts)
    existing_application = Application.objects.filter(
        user=user,
        scholarship=scholarship
    ).exclude(status='draft').first()
    
    if existing_application:
        messages.info(request, 'You have already submitted an application for this scholarship.')
        return redirect('users:dashboard')
    
    # Check for existing draft
    draft_application = Application.objects.filter(
        user=user,
        scholarship=scholarship,
        status='draft'
    ).first()

    if request.method == 'POST':
        action = request.POST.get('action', 'submit')
        
        # Get files from request or keep existing ones from draft
        passport = request.FILES.get('passport')
        photo = request.FILES.get('photo')
        graduation_certificate = request.FILES.get('graduation_certificate')
        # ... (get other files)
        
        if action == 'save_draft':
            # Create or update draft
            if not draft_application:
                draft_application = Application(user=user, scholarship=scholarship, status='draft')
            
            # Validate and update fields if new files provided
            for field_name in ['passport', 'photo', 'graduation_certificate', 'criminal_record',
                               'medical_examination', 'letter_of_recommendation_1',
                               'letter_of_recommendation_2', 'study_plan', 'english_certificate']:
                file = request.FILES.get(field_name)
                if file:
                    is_valid, error = validate_uploaded_file(file)
                    if not is_valid:
                        messages.error(request, error)
                        return render(request, 'scholarships/apply.html', {'scholarship': scholarship, 'application': draft_application})
                    setattr(draft_application, field_name, file)
            
            draft_application.save()
            messages.success(request, 'Application saved as draft.')
            return redirect('users:dashboard')

        elif action == 'submit':
            # Validate required files
            required_files = [
                'passport', 'photo', 'graduation_certificate', 'criminal_record',
                'medical_examination', 'letter_of_recommendation_1',
                'letter_of_recommendation_2', 'study_plan', 'english_certificate'
            ]
            
            # Check what's missing (checking both request.FILES and existing draft files)
            missing_files = []
            
            # Helper to check if file exists in draft
            def has_file(field_name):
                return draft_application and getattr(draft_application, field_name)

            if not request.FILES.get('passport') and not has_file('passport'): missing_files.append('Passport')
            if not request.FILES.get('photo') and not has_file('photo'): missing_files.append('Photo')
            if not request.FILES.get('graduation_certificate') and not has_file('graduation_certificate'): missing_files.append('Graduation Certificate')
            if not request.FILES.get('criminal_record') and not has_file('criminal_record'): missing_files.append('Criminal Record')
            if not request.FILES.get('medical_examination') and not has_file('medical_examination'): missing_files.append('Medical Examination')
            if not request.FILES.get('letter_of_recommendation_1') and not has_file('letter_of_recommendation_1'): missing_files.append('Letter Of Recommendation 1')
            if not request.FILES.get('letter_of_recommendation_2') and not has_file('letter_of_recommendation_2'): missing_files.append('Letter Of Recommendation 2')
            if not request.FILES.get('study_plan') and not has_file('study_plan'): missing_files.append('Study Plan')
            if not request.FILES.get('english_certificate') and not has_file('english_certificate'): missing_files.append('English Certificate')

            if missing_files:
                messages.error(request, f'Please upload all required documents: {", ".join(missing_files)}')
                return render(request, 'scholarships/apply.html', {'scholarship': scholarship, 'application': draft_application})
            
            try:
                # Create or update to pending
                if not draft_application:
                    draft_application = Application(user=user, scholarship=scholarship)
                
                draft_application.status = 'submitted'
                
                # Validate and assign files if provided
                for field_name in ['passport', 'photo', 'graduation_certificate', 'criminal_record',
                                   'medical_examination', 'letter_of_recommendation_1',
                                   'letter_of_recommendation_2', 'study_plan', 'english_certificate']:
                    file = request.FILES.get(field_name)
                    if file:
                        is_valid, error = validate_uploaded_file(file)
                        if not is_valid:
                            messages.error(request, error)
                            return render(request, 'scholarships/apply.html', {'scholarship': scholarship, 'application': draft_application})
                        setattr(draft_application, field_name, file)
                
                draft_application.save()
                
                messages.success(request, 'Your application has been submitted successfully! We will review it soon.')
                return redirect('users:dashboard')
            
            except Exception as e:
                messages.error(request, f'An error occurred while submitting your application: {str(e)}')
                return render(request, 'scholarships/apply.html', {'scholarship': scholarship, 'application': draft_application})
    
    context = {'scholarship': scholarship, 'application': draft_application}
    return render(request, 'scholarships/apply.html', context)


@login_required
def application_detail(request, app_id):
    """Display application details"""
    from finance.models import application_payment
    from .models import ApplicationStatusHistory

    # Get application and verify ownership
    application = get_object_or_404(Application, app_id=app_id, user=request.user)

    # Get payment information if exists
    payment = application_payment.objects.filter(application=application).first()

    # Get latest admission letter & JW02
    admission_letter = application.admission_letters.first()
    jw02 = application.jw02_forms.first()

    # Get status history
    status_history = ApplicationStatusHistory.objects.filter(application=application)

    # Progress stepper data
    PROGRESS_STEPS = [
        {'key': 'submitted', 'label': 'Submitted', 'icon': 'bi-send-check'},
        {'key': 'under_review', 'label': 'Under Review', 'icon': 'bi-search'},
        {'key': 'documents_verified', 'label': 'Docs Verified', 'icon': 'bi-file-earmark-check'},
        {'key': 'payment', 'label': 'Payment', 'icon': 'bi-credit-card'},
        {'key': 'payment_verified', 'label': 'Payment Verified', 'icon': 'bi-patch-check'},
        {'key': 'approved', 'label': 'Approved', 'icon': 'bi-hand-thumbs-up'},
        {'key': 'in_progress', 'label': 'Processing', 'icon': 'bi-gear'},
        {'key': 'admission_letter', 'label': 'Admission Letter', 'icon': 'bi-envelope-paper'},
        {'key': 'jw02', 'label': 'JW02 Form', 'icon': 'bi-file-earmark-ruled'},
        {'key': 'complete', 'label': 'Complete', 'icon': 'bi-trophy'},
    ]

    # Map status to step index
    STATUS_TO_STEP = {
        'draft': -1,
        'submitted': 0,
        'under_review': 1,
        'documents_verified': 2,
        'payment_verified': 4,
        'approved': 5,
        'in_progress': 6,
        'admission_letter_uploaded': 7,
        'admission_letter_approved': 7,
        'jw02_uploaded': 8,
        'jw02_approved': 8,
        'complete': 9,
        'rejected': -2,
        'letter_pending': 7,
        'jw02_pending': 8,
    }

    current_step_index = STATUS_TO_STEP.get(application.status, -1)
    
    # Check if payment has been made (even if not verified yet)
    payment_made = payment is not None and payment.receipt_pdf

    # Mark steps as completed, current, or pending
    for i, step in enumerate(PROGRESS_STEPS):
        if application.status == 'rejected':
            step['state'] = 'rejected'
        elif i < current_step_index:
            step['state'] = 'completed'
        elif i == current_step_index:
            step['state'] = 'current'
        else:
            step['state'] = 'pending'
        
        # Special case: payment step (index 3)
        if step['key'] == 'payment':
            if payment_made:
                step['state'] = 'completed'
            elif current_step_index == 2:  # documents_verified
                step['state'] = 'action'  # needs user action
            elif current_step_index > 3:
                step['state'] = 'completed'

    # What's Next guidance
    WHATS_NEXT = {
        'draft': {
            'title': 'Complete Your Application',
            'message': 'Your application is saved as a draft. Submit it when you are ready to proceed.',
            'color': 'secondary',
            'icon': 'bi-pencil-square',
        },
        'submitted': {
            'title': 'Application Submitted',
            'message': 'Your application has been received and is in the queue for review. Our office team will check your documents shortly.',
            'color': 'primary',
            'icon': 'bi-clock-history',
        },
        'under_review': {
            'title': 'Documents Under Review',
            'message': 'Our office team is currently reviewing your submitted documents. You will be notified once the review is complete.',
            'color': 'info',
            'icon': 'bi-search',
        },
        'documents_verified': {
            'title': 'Action Required: Make Payment',
            'message': 'Great news! Your documents have been verified. Please proceed with the payment to continue your application.',
            'color': 'success',
            'icon': 'bi-credit-card',
            'action': True,
        },
        'payment_verified': {
            'title': 'Payment Verified',
            'message': 'Your payment has been verified. Your application is now being reviewed by our agent team for final approval.',
            'color': 'info',
            'icon': 'bi-patch-check',
        },
        'approved': {
            'title': 'Application Approved',
            'message': 'Your application has been approved and forwarded to our headquarters for university processing. Please allow some time for the next steps.',
            'color': 'success',
            'icon': 'bi-hand-thumbs-up',
        },
        'in_progress': {
            'title': 'University Application in Progress',
            'message': 'Your university application is currently being processed by our team. We will upload your admission letter once it is received.',
            'color': 'warning',
            'icon': 'bi-gear',
        },
        'admission_letter_uploaded': {
            'title': 'Admission Letter Received',
            'message': 'Your admission letter has been uploaded and is awaiting verification. You will be notified once it is approved and available for download.',
            'color': 'primary',
            'icon': 'bi-envelope-paper',
        },
        'admission_letter_approved': {
            'title': 'Admission Letter Approved',
            'message': 'Your admission letter has been approved! You can download it from the section below. We are now processing your JW02 form.',
            'color': 'success',
            'icon': 'bi-check-circle',
        },
        'jw02_uploaded': {
            'title': 'JW02 Form Received',
            'message': 'Your JW02 form has been uploaded and is awaiting verification. You will be notified once it is approved.',
            'color': 'primary',
            'icon': 'bi-file-earmark-ruled',
        },
        'jw02_approved': {
            'title': 'JW02 Form Approved',
            'message': 'Your JW02 form has been approved! Your application is nearly complete.',
            'color': 'success',
            'icon': 'bi-check-circle',
        },
        'complete': {
            'title': 'Application Complete!',
            'message': 'Congratulations! Your application process is complete. You can download your admission letter and JW02 form below.',
            'color': 'dark',
            'icon': 'bi-trophy',
        },
        'rejected': {
            'title': 'Application Rejected',
            'message': 'Unfortunately, your application has been rejected. Please review the rejection reason below.',
            'color': 'danger',
            'icon': 'bi-x-circle',
        },
        'letter_pending': {
            'title': 'Admission Letter Needs Revision',
            'message': 'Your admission letter requires revision. Our team is working on getting the updated version.',
            'color': 'warning',
            'icon': 'bi-exclamation-triangle',
        },
        'jw02_pending': {
            'title': 'JW02 Form Needs Revision',
            'message': 'Your JW02 form requires revision. Our team is working on getting the updated version.',
            'color': 'warning',
            'icon': 'bi-exclamation-triangle',
        },
    }

    whats_next = WHATS_NEXT.get(application.status, {
        'title': 'Processing',
        'message': 'Your application is being processed.',
        'color': 'info',
        'icon': 'bi-hourglass-split',
    })

    # Override message if docs verified but payment already made
    if application.status == 'documents_verified' and payment_made:
        whats_next = {
            'title': 'Payment Submitted',
            'message': 'Your payment receipt has been submitted and is awaiting verification by our office team.',
            'color': 'info',
            'icon': 'bi-hourglass-split',
        }

    # Progress percentage
    total_steps = len(PROGRESS_STEPS)
    if application.status == 'rejected':
        progress_percent = 0
    elif current_step_index >= 0:
        progress_percent = int(((current_step_index + 1) / total_steps) * 100)
    else:
        progress_percent = 0

    context = {
        'application': application,
        'payment': payment,
        'admission_letter': admission_letter,
        'jw02': jw02,
        'status_history': status_history,
        'progress_steps': PROGRESS_STEPS,
        'whats_next': whats_next,
        'progress_percent': progress_percent,
        'payment_made': payment_made,
    }

    return render(request, 'scholarships/application_detail.html', context)
