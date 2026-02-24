from django.db import models
from django.conf import settings

def get_upload_path(instance, filename):
    """
    Generate upload path with username prefix: username-app_id-filename
    """
    username = instance.user.username
    app_id = instance.app_id if instance.app_id else 'new'
    return f"applications/{username}-{app_id}-{filename}"

def get_admission_letter_path(instance, filename):
    username = instance.application.user.username
    app_id = instance.application.app_id
    return f"admission_letters/{username}-{app_id}-{filename}"

def get_jw02_path(instance, filename):
    username = instance.application.user.username
    app_id = instance.application.app_id
    return f"jw02_forms/{username}-{app_id}-{filename}"


class scholarships(models.Model):
    DEGREE_CHOICES = [
        ('bachelor', 'Bachelor'),
        ('master', 'Master'),
        ('phd', 'PhD'),
    ]
    
    SEMESTER_CHOICES = [
        ('fall', 'Fall'),
        ('spring', 'Spring'),
        ('summer', 'Summer'),
    ]
    
    SCHOLARSHIP_TYPE_CHOICES = [
        ('full', 'Full Scholarship'),
        ('partial', 'Partial Scholarship'),
        ('merit', 'Merit Based'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    city = models.CharField(max_length=100)
    major = models.CharField(max_length=100)
    degree = models.CharField(max_length=50, choices=DEGREE_CHOICES)
    language = models.CharField(max_length=100)
    scholarship_type = models.CharField(max_length=50, choices=SCHOLARSHIP_TYPE_CHOICES)
    deadline = models.DateField()
    semester = models.CharField(max_length=20, choices=SEMESTER_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    eligibility = models.TextField()
    note = models.TextField(blank=True, null=True)
    
    # Commission fields (set by Admin per scholarship)
    agent_commission = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Amount (USD) the Main Agent earns per completed application"
    )
    hq_commission = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Amount (USD) HQ earns per completed application"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "scholarships"


class Application(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('documents_verified', 'Documents Verified'),
        ('payment_verified', 'Payment Verified'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('in_progress', 'In Progress'),
        ('admission_letter_uploaded', 'Admission Letter Uploaded'),
        ('admission_letter_approved', 'Admission Letter Approved'),
        ('jw02_uploaded', 'JW02 Uploaded'),
        ('jw02_approved', 'JW02 Approved'),
        ('letter_pending', 'Letter Pending Revision'),
        ('jw02_pending', 'JW02 Pending Revision'),
        ('complete', 'Complete'),
    ]

    app_id = models.AutoField(primary_key=True)
    scholarship = models.ForeignKey(scholarships, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='applications')
    office = models.ForeignKey(
        'office.Office', on_delete=models.SET_NULL,
        blank=True, null=True, related_name='applications',
        help_text='Branch office that owns/created this application.',
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    applied_date = models.DateTimeField(auto_now_add=True)
    
    # Documents
    passport = models.FileField(upload_to=get_upload_path, blank=True, null=True)
    photo = models.FileField(upload_to=get_upload_path, blank=True, null=True)
    graduation_certificate = models.FileField(upload_to=get_upload_path, blank=True, null=True)
    criminal_record = models.FileField(upload_to=get_upload_path, blank=True, null=True)
    medical_examination = models.FileField(upload_to=get_upload_path, blank=True, null=True)
    letter_of_recommendation_1 = models.FileField(upload_to=get_upload_path, blank=True, null=True)
    letter_of_recommendation_2 = models.FileField(upload_to=get_upload_path, blank=True, null=True)
    study_plan = models.FileField(upload_to=get_upload_path, blank=True, null=True)
    english_certificate = models.FileField(upload_to=get_upload_path, blank=True, null=True)
    
    # Workflow fields
    rejection_reason = models.TextField(blank=True, null=True)
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        blank=True, null=True, related_name='assigned_applications'
    )
    assigned_hq = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        blank=True, null=True, related_name='hq_applications'
    )
    deadline = models.DateTimeField(blank=True, null=True, help_text="Deadline for HQ to complete university application")
    approved_date = models.DateTimeField(blank=True, null=True)
    completed_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.scholarship.name}"
    
    class Meta:
        db_table = 'applications'


class AdmissionLetter(models.Model):
    STATUS_CHOICES = [
        ('pending_verification', 'Pending Verification'),
        ('approved', 'Approved'),
        ('revision_requested', 'Revision Requested'),
    ]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='admission_letters')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='uploaded_admission_letters'
    )
    file = models.FileField(upload_to=get_admission_letter_path)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_verification')
    revision_note = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        blank=True, null=True, related_name='approved_admission_letters'
    )

    def __str__(self):
        return f"Admission Letter for {self.application} - {self.get_status_display()}"

    class Meta:
        db_table = 'admission_letters'
        ordering = ['-uploaded_at']


class JW02Form(models.Model):
    STATUS_CHOICES = [
        ('pending_verification', 'Pending Verification'),
        ('approved', 'Approved'),
        ('revision_requested', 'Revision Requested'),
    ]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='jw02_forms')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='uploaded_jw02_forms'
    )
    file = models.FileField(upload_to=get_jw02_path)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_verification')
    revision_note = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        blank=True, null=True, related_name='approved_jw02_forms'
    )

    def __str__(self):
        return f"JW02 Form for {self.application} - {self.get_status_display()}"

    class Meta:
        db_table = 'jw02_forms'
        ordering = ['-uploaded_at']


class ApplicationStatusHistory(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=30, blank=True, null=True)
    new_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='status_changes'
    )
    note = models.TextField(blank=True, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.application} : {self.old_status} → {self.new_status}"

    class Meta:
        db_table = 'application_status_history'
        ordering = ['-changed_at']
        verbose_name_plural = "Application status histories"
    
