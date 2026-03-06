from django.urls import path
from . import views

app_name = 'devtools'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('logs/', views.log_viewer, name='log_viewer'),
    path('requests/', views.request_log, name='request_log'),
    path('submissions/', views.submission_tracker, name='submission_tracker'),
    path('health/', views.health_check, name='health_check'),

    # API endpoints for AJAX
    path('api/logs/', views.api_logs, name='api_logs'),
    path('api/requests/', views.api_requests, name='api_requests'),
    path('api/health/', views.api_health, name='api_health'),
]
