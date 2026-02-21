from django.urls import path
from . import views

app_name = 'headquarters'

urlpatterns = [
    # Auth
    path('login/', views.hq_login, name='login'),
    path('logout/', views.hq_logout, name='logout'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Applications
    path('applications/', views.application_list, name='application_list'),
    path('applications/<int:app_id>/', views.application_detail, name='application_detail'),
    path('applications/<int:app_id>/download-docs/', views.download_documents, name='download_documents'),
    path('applications/<int:app_id>/mark-applied/', views.mark_applied, name='mark_applied'),
    path('applications/<int:app_id>/upload-letter/', views.upload_admission_letter, name='upload_admission_letter'),

    # JW02
    path('jw02/<int:app_id>/', views.upload_jw02, name='upload_jw02'),

    # Revisions
    path('revisions/', views.revision_list, name='revision_list'),
    path('revisions/<int:letter_id>/reupload/', views.reupload_letter, name='reupload_letter'),
    path('revisions/jw02/<int:jw02_id>/reupload/', views.reupload_jw02, name='reupload_jw02'),

    # Wallet
    path('wallet/', views.wallet_page, name='wallet'),
    path('wallet/withdraw/', views.request_withdrawal, name='request_withdrawal'),

    # Notifications
    path('notifications/', views.hq_notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.hq_mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.hq_mark_all_read, name='mark_all_read'),
]
