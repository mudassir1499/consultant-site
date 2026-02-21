from django.shortcuts import render, redirect
from django.contrib import messages
from scholarships.models import scholarships, Application
from users.models import User

# Create your views here.
def home(request):
    scholarships_list = scholarships.objects.all()[:6]  # Get first 6 scholarships
    
    # Get applied scholarships for logged-in user
    applied_scholarship_ids = []
    
    if request.user.is_authenticated:
        applied_scholarship_ids = list(
            Application.objects.filter(user=request.user)
            .values_list('scholarship_id', flat=True)
        )
    
    context = {
        'scholarships': scholarships_list,
        'applied_scholarship_ids': applied_scholarship_ids,
    }
    return render(request, 'pages/home.html', context) 

def about(request):
    return render(request, 'pages/about.html')


def contact(request):
    """Contact page with simple contact form"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message_text = request.POST.get('message', '').strip()

        if not all([name, email, message_text]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'pages/contact.html')

        # Try to send email (fails silently if email is not configured)
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                subject=f'[Contact Form] {subject or "No Subject"}',
                message=f'From: {name} <{email}>\n\n{message_text}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.EMAIL_HOST_USER] if settings.EMAIL_HOST_USER else [],
                fail_silently=True,
            )
        except Exception:
            pass

        messages.success(request, 'Thank you for your message! We will get back to you soon.')
        return redirect('pages:contact')

    return render(request, 'pages/contact.html')    