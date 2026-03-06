from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
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
        'page_title': 'Guaranteed Scholarships in China | DFS Education',
        'page_description': 'DFS Education provides guaranteed scholarships in China for international students. Expert guidance from application to admission at top Chinese universities.',
    }
    return render(request, 'pages/home.html', context) 

def about(request):
    context = {
        'page_title': 'About Us \u2014 DFS Education',
        'page_description': 'Learn about DFS Education, a trusted consultancy providing guaranteed scholarships in China. 10+ years experience, 1000+ students helped, 95% success rate.',
    }
    return render(request, 'pages/about.html', context)


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

    return render(request, 'pages/contact.html', {
        'page_title': 'Contact Us \u2014 DFS Education',
        'page_description': 'Get in touch with DFS Education for scholarship enquiries, application support, and consultancy services for studying in China.',
    })


def robots_txt(request):
    """Serve robots.txt as plain text."""
    content = render_to_string('robots.txt')
    return HttpResponse(content, content_type='text/plain')