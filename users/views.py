from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from .models import User

def register(request):
    """Handle user registration"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()

        # Force role to 'user' — other roles are invitation-only
        role = 'user'

        # Validation
        if not all([username, email, password]):
            messages.error(request, 'Username, email, and password are required.')
            return render(request, 'users/register.html')

        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'users/register.html')

        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters long.')
            return render(request, 'users/register.html')

        try:
            # Create user using create_user helper (standard Django method)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
                first_name=first_name,
                last_name=last_name,
                phone=phone
            )
            messages.success(request, 'Registration successful! Please login.')
            return redirect('users:login')
        except Exception as e:
            messages.error(request, str(e))
            return render(request, 'users/register.html')

    return render(request, 'users/register.html')


@require_http_methods(["GET", "POST"])
def user_login(request):
    """Handle user login"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not all([username, password]):
            messages.error(request, 'Username and password are required.')
            return render(request, 'users/login.html')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                
                # Handle next parameter
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                
                # Redirect based on role
                if user.role == 'office':
                    return redirect('office:office_dashboard')
                elif user.role == 'agent':
                    return redirect('agent:dashboard')
                elif user.role == 'headquarters':
                    return redirect('headquarters:dashboard')
                elif user.is_superuser:
                    return redirect('/admin/')
                
                return redirect('users:dashboard')
            else:
                messages.error(request, 'Your account is inactive.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'users/login.html')


@require_POST
def user_logout(request):
    """Handle user logout (POST only for CSRF safety)"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('users:login')


@login_required
def user_profile(request):
    """Display and edit user profile"""
    user = request.user
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()

        # Validate email uniqueness (excluding current user)
        if email and User.objects.filter(email=email).exclude(pk=user.pk).exists():
            messages.error(request, 'This email is already in use.')
            return render(request, 'users/profile.html', {'user': user})

        user.first_name = first_name
        user.last_name = last_name
        if email:
            user.email = email
        user.phone = phone
        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('users:profile')

    return render(request, 'users/profile.html', {'user': user})




@login_required
def dashboard(request):
    """Display user dashboard"""
    from scholarships.models import Application
    from finance.models import application_payment
    
    user = request.user
    
    # Status to step mapping for progress tracking
    STATUS_STEP_MAP = {
        'draft': 0,
        'submitted': 1,
        'under_review': 2,
        'documents_verified': 3,
        'payment_verified': 4,
        'approved': 5,
        'in_progress': 6,
        'admission_letter_uploaded': 7,
        'admission_letter_approved': 8,
        'jw02_uploaded': 9,
        'jw02_approved': 10,
        'complete': 11,
        'rejected': -1,
        'letter_pending': 7,
        'jw02_pending': 9,
    }
    TOTAL_STEPS = 11  # complete = step 11

    # User-friendly status messages
    STATUS_MESSAGES = {
        'draft': 'Your application is saved as a draft.',
        'submitted': 'Your application has been submitted and is awaiting review.',
        'under_review': 'Your documents are being reviewed by our office team.',
        'documents_verified': 'Your documents have been verified. Please make the payment to proceed.',
        'payment_verified': 'Your payment has been verified. Your application is being reviewed by our agent.',
        'approved': 'Your application has been approved and forwarded for processing.',
        'in_progress': 'Your university application is being processed.',
        'admission_letter_uploaded': 'Your admission letter has been uploaded and is awaiting approval.',
        'admission_letter_approved': 'Your admission letter has been approved. Waiting for JW02 form.',
        'jw02_uploaded': 'Your JW02 form has been uploaded and is awaiting approval.',
        'jw02_approved': 'Your JW02 form has been approved. Application is almost complete!',
        'complete': 'Congratulations! Your application is complete.',
        'rejected': 'Your application has been rejected.',
        'letter_pending': 'Your admission letter needs revision.',
        'jw02_pending': 'Your JW02 form needs revision. Our team is working on the updated version.',
    }

    # Statuses that require user action
    ACTION_STATUSES = {
        'draft': {'label': 'Complete Application', 'icon': 'bi-pencil-square', 'color': 'secondary'},
        'documents_verified': {'label': 'Make Payment', 'icon': 'bi-credit-card', 'color': 'success'},
    }
    
    # Get user's applications
    applications = Application.objects.filter(user=user).order_by('-applied_date')
    
    # Attach payment, admission letter, JW02, progress info to each application
    for app in applications:
        payment = application_payment.objects.filter(application=app).first()
        app.payment = payment
        app.latest_admission_letter = app.admission_letters.first()
        app.latest_jw02 = app.jw02_forms.first()
        
        # Progress calculation
        step = STATUS_STEP_MAP.get(app.status, 0)
        if step >= 0:
            app.progress_percent = int((step / TOTAL_STEPS) * 100)
        else:
            app.progress_percent = 0
        app.current_step = step
        app.status_message = STATUS_MESSAGES.get(app.status, '')
        
        # Action required info
        action = ACTION_STATUSES.get(app.status)
        if app.status == 'documents_verified' and app.payment and app.payment.receipt_pdf:
            action = None  # Already paid, waiting for verification
            app.status_message = 'Payment submitted. Waiting for verification.'
        app.action_info = action
    
    # Get stats
    in_progress_statuses = ['submitted', 'under_review', 'documents_verified', 'payment_verified', 'in_progress',
                            'admission_letter_uploaded', 'admission_letter_approved', 'jw02_uploaded', 'jw02_approved', 'letter_pending', 'jw02_pending']
    pending_apps = applications.filter(status__in=in_progress_statuses).count()
    approved_apps = applications.filter(status='approved').count()
    rejected_apps = applications.filter(status='rejected').count()
    completed_apps = applications.filter(status='complete').count()
    draft_apps = applications.filter(status='draft').count()
    needs_action = sum(1 for app in applications if app.action_info is not None)
    
    context = {
        'user': user,
        'applications': applications,
        'pending_count': pending_apps,
        'approved_count': approved_apps,
        'rejected_count': rejected_apps,
        'completed_count': completed_apps,
        'draft_count': draft_apps,
        'needs_action_count': needs_action,
    }
    return render(request, 'users/dashboard.html', context)


@login_required
def notification_list(request):
    """Display all notifications for the logged-in user"""
    from django.core.paginator import Paginator
    from .models import Notification
    notifications_qs = Notification.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(notifications_qs, 20)
    page_number = request.GET.get('page')
    notifications = paginator.get_page(page_number)
    return render(request, 'users/notifications.html', {'notifications': notifications})


@login_required
def mark_notification_read(request, notification_id):
    """Mark a single notification as read, then redirect to its link"""
    from .models import Notification
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    if notification.link:
        return redirect(notification.link)
    return redirect('users:notifications')


@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    from .models import Notification
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('users:notifications')
