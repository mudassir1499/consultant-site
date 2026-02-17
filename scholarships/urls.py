from django.urls import path
from . import views

app_name = 'scholarships'

urlpatterns = [
    path('apply/<int:scholarship_id>/', views.apply_scholarship, name='apply'),
    path('application/<int:app_id>/', views.application_detail, name='detail'),
]
