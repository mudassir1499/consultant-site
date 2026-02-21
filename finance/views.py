from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from scholarships.models import Application
from django.contrib.auth.decorators import login_required
from .models import bank_account, application_payment
import uuid

@login_required
def application_payment_page(request, application_id):
    """Display payment page for scholarship application"""
    
    # Get application
    application = get_object_or_404(Application, app_id=application_id)
    
    # Verify user owns this application
    if application.user != request.user:
        messages.error(request, 'You do not have permission to access this application.')
        return redirect('users:dashboard')
    
    # Get active bank accounts
    bank_accounts = bank_account.objects.filter(status='active')
    
    if not bank_accounts.exists():
        messages.error(request, 'No payment accounts available at the moment.')
        return redirect('users:dashboard')
    
    context = {
        'application': application,
        'bank_accounts': bank_accounts,
        'scholarship_amount': application.scholarship.price,
    }
    return render(request, 'finance/application-payment.html', context)


@login_required
def process_payment(request, application_id):
    """Process payment submission"""
    
    if request.method != 'POST':
        return redirect('finance:payment', application_id=application_id)
    
    # Get application
    application = get_object_or_404(Application, app_id=application_id)
    
    # Verify user owns this application
    if application.user != request.user:
        messages.error(request, 'You do not have permission to access this application.')
        return redirect('users:dashboard')
    
    # Status guard — only allow payment when documents are verified
    if application.status != 'documents_verified':
        messages.error(request, 'Payment is not available for this application at its current stage.')
        return redirect('users:dashboard')
    
    # Validate file upload
    if 'receipt' not in request.FILES:
        messages.error(request, 'Please upload a payment receipt.')
        return redirect('finance:payment', application_id=application_id)
    
    receipt_file = request.FILES['receipt']
    
    # Validate file size (max 5MB)
    if receipt_file.size > 5 * 1024 * 1024:
        messages.error(request, 'Receipt file size must be less than 5MB.')
        return redirect('finance:payment', application_id=application_id)
    
    # Validate file type
    allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png']
    file_ext = receipt_file.name.split('.')[-1].lower()
    if file_ext not in allowed_extensions:
        messages.error(request, 'Receipt must be PDF, JPG, or PNG.')
        return redirect('finance:payment', application_id=application_id)
    
    try:
        # Create payment record
        transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        
        payment = application_payment.objects.create(
            application=application,
            amount=application.scholarship.price,
            receipt_pdf=receipt_file,
            payment_status='pending',
            transaction_id=transaction_id,
        )
        
        messages.success(request, f'Payment submitted successfully! Transaction ID: {transaction_id}')
        return redirect('finance:payment-success')
    
    except Exception as e:
        messages.error(request, f'An error occurred while processing your payment: {str(e)}')
        return redirect('finance:payment', application_id=application_id)


@login_required
def payment_success(request):
    """Display payment success page"""
    return render(request, 'finance/payment-success.html')
