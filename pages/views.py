from django.shortcuts import render
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