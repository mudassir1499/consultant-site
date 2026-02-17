from django.urls import path
from . import views

app_name = 'agent'

urlpatterns = [
    # Auth
    path('login/', views.agent_login, name='login'),
    path('logout/', views.agent_logout, name='logout'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Applications
    path('applications/', views.application_list, name='application_list'),
    path('applications/<int:app_id>/', views.application_detail, name='application_detail'),
    path('applications/<int:app_id>/approve/', views.approve_application, name='approve_application'),
    path('applications/<int:app_id>/reject/', views.reject_application, name='reject_application'),

    # Admission Letters
    path('admission-letter/<int:app_id>/', views.admission_letter_review, name='admission_letter_review'),
    path('admission-letter/<int:app_id>/approve/', views.approve_admission_letter, name='approve_admission_letter'),
    path('admission-letter/<int:app_id>/request-revision/', views.request_revision, name='request_revision'),

    # JW02
    path('jw02/<int:app_id>/', views.jw02_review, name='jw02_review'),
    path('jw02/<int:app_id>/approve/', views.approve_jw02, name='approve_jw02'),
    path('jw02/<int:app_id>/request-revision/', views.request_jw02_revision, name='request_jw02_revision'),

    # Wallet
    path('wallet/', views.wallet_page, name='wallet'),
    path('wallet/withdraw/', views.request_withdrawal, name='request_withdrawal'),
]
