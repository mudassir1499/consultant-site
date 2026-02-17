from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('payment/<int:application_id>/', views.application_payment_page, name='payment'),
    path('process-payment/<int:application_id>/', views.process_payment, name='process_payment'),
    path('payment-success/', views.payment_success, name='payment-success'),
]
