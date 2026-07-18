from django.urls import path
from . import views

app_name = 'admin_portal'

urlpatterns = [
    # Dashboard
    path('', views.admin_dashboard, name='dashboard'),
    
    # Applications
    path('applications/', views.admin_application_list, name='application_list'),
    path('applications/<int:app_id>/', views.admin_application_detail, name='application_detail'),
    path('applications/<int:app_id>/download-documents/', views.admin_download_documents, name='download_documents'),
    path('applications/<int:app_id>/verify-documents/', views.admin_verify_documents, name='verify_documents'),
    path('applications/<int:app_id>/verify-payment/', views.admin_verify_payment, name='verify_payment'),
    path('applications/<int:app_id>/approve/', views.admin_approve_application, name='approve_application'),
    path('applications/<int:app_id>/reject/', views.admin_reject_application, name='reject_application'),
    path('applications/<int:app_id>/upload-letter/', views.admin_upload_admission_letter, name='upload_admission_letter'),
    path('applications/<int:app_id>/upload-jw02/', views.admin_upload_jw02, name='upload_jw02'),
    path('applications/<int:app_id>/reupload-letter/<int:letter_id>/', views.admin_reupload_letter, name='reupload_letter'),
    path('applications/<int:app_id>/reupload-jw02/<int:jw02_id>/', views.admin_reupload_jw02, name='reupload_jw02'),
    
    # Payments
    path('payments/', views.admin_payment_list, name='payment_list'),
    path('payments/<int:payment_id>/', views.admin_payment_detail, name='payment_detail'),
    path('payments/<int:payment_id>/approve/', views.admin_approve_payment, name='approve_payment'),
    path('payments/<int:payment_id>/reject/', views.admin_reject_payment, name='reject_payment'),
    
    # Users
    path('students/', views.admin_student_list, name='student_list'),
    path('offices/', views.admin_office_list, name='office_list'),
    path('agents/', views.admin_agent_list, name='agent_list'),
    path('hq/', views.admin_hq_list, name='hq_list'),

    # User management (create / edit / status / password / delete)
    path('users/create/', views.admin_user_create, name='user_create'),
    path('users/<int:user_id>/edit/', views.admin_user_edit, name='user_edit'),
    path('users/<int:user_id>/toggle-status/', views.admin_user_toggle_status, name='user_toggle_status'),
    path('users/<int:user_id>/reset-password/', views.admin_user_reset_password, name='user_reset_password'),
    path('users/<int:user_id>/delete/', views.admin_user_delete, name='user_delete'),

    # Office & region management
    path('offices/create/', views.admin_office_create, name='office_create'),
    path('offices/<int:office_id>/edit/', views.admin_office_edit, name='office_edit'),
    path('offices/<int:office_id>/delete/', views.admin_office_delete, name='office_delete'),
    path('offices/<int:office_id>/regions/add/', views.admin_office_region_add, name='office_region_add'),
    path('regions/<int:region_id>/delete/', views.admin_office_region_delete, name='office_region_delete'),

    # Bank accounts
    path('banks/', views.admin_bank_list, name='bank_list'),
    path('banks/create/', views.admin_bank_create, name='bank_create'),
    path('banks/<int:account_id>/edit/', views.admin_bank_edit, name='bank_edit'),
    path('banks/<int:account_id>/delete/', views.admin_bank_delete, name='bank_delete'),

    # Site settings
    path('settings/', views.admin_site_settings, name='site_settings'),
    
    # Withdrawals
    path('withdrawals/', views.admin_withdrawal_list, name='withdrawal_list'),
    path('withdrawals/<int:withdrawal_id>/approve/', views.admin_approve_withdrawal, name='approve_withdrawal'),
    path('withdrawals/<int:withdrawal_id>/reject/', views.admin_reject_withdrawal, name='reject_withdrawal'),
    
    # Bulk Actions
    path('applications/bulk-action/', views.admin_bulk_action, name='bulk_action'),
    path('payments/bulk-action/', views.admin_bulk_payment_action, name='bulk_payment_action'),
    
    # Scholarships
    path('scholarships/', views.admin_scholarship_list, name='scholarship_list'),
    path('scholarships/create/', views.admin_scholarship_create, name='scholarship_create'),
    path('scholarships/<int:scholarship_id>/', views.admin_scholarship_detail, name='scholarship_detail'),
    path('scholarships/<int:scholarship_id>/edit/', views.admin_scholarship_edit, name='scholarship_edit'),
    path('scholarships/<int:scholarship_id>/delete/', views.admin_scholarship_delete, name='scholarship_delete'),
    
    # CSV Export
    path('applications/export-csv/', views.admin_export_applications_csv, name='export_applications_csv'),
    path('payments/export-csv/', views.admin_export_payments_csv, name='export_payments_csv'),
]
