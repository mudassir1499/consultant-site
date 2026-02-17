from django.urls import path
from . import views

app_name = 'office'

urlpatterns = [
    # Auth
    path('login/', views.office_login, name='login'),
    path('logout/', views.office_logout, name='logout'),

    # Dashboard
    path('', views.office_dashboard, name='office_dashboard'),

    # Applications
    path('applications/', views.application_list, name='application_list'),
    path('applications/create/', views.create_application, name='create_application'),
    path('applications/<int:app_id>/', views.application_detail, name='application_detail'),
    path('applications/<int:app_id>/upload-documents/', views.upload_documents, name='upload_documents'),
    path('applications/<int:app_id>/submit/', views.submit_application, name='submit_application'),
    path('applications/<int:app_id>/start-review/', views.start_review, name='start_review'),
    path('applications/<int:app_id>/verify-documents/', views.verify_documents, name='verify_documents'),
    path('applications/<int:app_id>/verify-payment/', views.verify_payment, name='verify_payment'),
    path('applications/<int:app_id>/forward-to-agent/', views.forward_to_agent, name='forward_to_agent'),

    # Payments
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/<int:payment_id>/', views.payment_detail, name='payment_detail'),
    path('payments/<int:payment_id>/approve/', views.approve_payment, name='approve_payment'),
    path('payments/<int:payment_id>/reject/', views.reject_payment, name='reject_payment'),
    path('applications/<int:app_id>/make-payment/', views.make_payment, name='make_payment'),

    # Users
    path('users/', views.user_list, name='user_list'),

    # Notifications
    path('notifications/', views.office_notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.office_mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.office_mark_all_read, name='mark_all_read'),
]