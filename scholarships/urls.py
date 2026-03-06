from django.urls import path
from . import views

app_name = 'scholarships'

urlpatterns = [
    path('', views.scholarship_list, name='scholarship_list'),
    # Slug-based scholarship detail (SEO-friendly)
    path('<slug:slug>/', views.scholarship_detail, name='scholarship_detail'),
    path('apply/<int:scholarship_id>/', views.apply_scholarship, name='apply'),
    path('application/<int:app_id>/', views.application_detail, name='detail'),
    # 301 redirect for old ID-based URLs
    path('id/<int:scholarship_id>/', views.scholarship_detail_redirect, name='scholarship_detail_legacy'),
]
