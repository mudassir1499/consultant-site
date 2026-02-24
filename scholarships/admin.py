from django.contrib import admin
from django.utils.html import format_html
from .models import scholarships, Application, AdmissionLetter, JW02Form, ApplicationStatusHistory


class ApplicationInline(admin.TabularInline):
    """Recent applications for this scholarship"""
    model = Application
    fields = ['app_id', 'user', 'office', 'status', 'applied_date']
    readonly_fields = ['app_id', 'user', 'office', 'status', 'applied_date']
    extra = 0
    max_num = 0
    show_change_link = True
    verbose_name = 'Application'
    verbose_name_plural = 'Recent Applications'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'office').order_by('-applied_date')[:10]


@admin.register(scholarships)
class ScholarshipsAdmin(admin.ModelAdmin):
    list_display = ['name', 'degree_badge', 'type_badge', 'city', 'major', 'price_display', 'deadline', 'application_count']
    list_filter = ['degree', 'scholarship_type', 'semester', 'language']
    search_fields = ['name', 'major', 'city', 'description']
    readonly_fields = ['id', 'application_count_display']
    list_per_page = 25
    save_on_top = True

    fieldsets = (
        (None, {
            'fields': ('name', 'description'),
            'description': (
                '<strong>📚 Scholarship Details</strong><br>'
                'Enter the scholarship name and a detailed description. '
                'This information is visible to students on the website.'
            ),
        }),
        ('🎓 Academic Information', {
            'fields': ('degree', 'major', 'language', 'scholarship_type', 'semester'),
            'description': 'Degree level, field of study, and scholarship type.',
        }),
        ('📍 Location & Schedule', {
            'fields': ('city', 'deadline'),
            'description': 'University city and application deadline.',
        }),
        ('💰 Pricing & Commissions', {
            'fields': ('price', 'agent_commission', 'hq_commission'),
            'description': (
                '<strong>Price:</strong> Amount the student pays for this scholarship application.<br>'
                '<strong>Agent Commission:</strong> Amount earned by the Main Agent upon successful completion.<br>'
                '<strong>HQ Commission:</strong> Amount earned by Headquarters upon successful completion.<br>'
                '<em>Commissions are only credited after the application reaches "Complete" status.</em>'
            ),
        }),
        ('📋 Additional Info', {
            'fields': ('eligibility', 'note'),
            'description': 'Eligibility requirements and admin notes.',
        }),
        ('📊 Statistics', {
            'fields': ('application_count_display',),
        }),
    )

    inlines = [ApplicationInline]

    def degree_badge(self, obj):
        colors = {'bachelor': '#198754', 'master': '#0d6efd', 'phd': '#6f42c1'}
        color = colors.get(obj.degree, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;">{}</span>',
            color, obj.get_degree_display(),
        )
    degree_badge.short_description = 'Degree'
    degree_badge.admin_order_field = 'degree'

    def type_badge(self, obj):
        colors = {'full': '#198754', 'partial': '#fd7e14', 'merit': '#6f42c1'}
        color = colors.get(obj.scholarship_type, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;">{}</span>',
            color, obj.get_scholarship_type_display(),
        )
    type_badge.short_description = 'Type'
    type_badge.admin_order_field = 'scholarship_type'

    def price_display(self, obj):
        return format_html('<strong>${:,.2f}</strong>', obj.price)
    price_display.short_description = 'Price'
    price_display.admin_order_field = 'price'

    def application_count(self, obj):
        return obj.application_set.count()
    application_count.short_description = 'Apps'

    def application_count_display(self, obj):
        total = obj.application_set.count()
        active = obj.application_set.exclude(status__in=['complete', 'rejected', 'draft']).count()
        complete = obj.application_set.filter(status='complete').count()
        return format_html(
            '<strong>{}</strong> Total &nbsp;|&nbsp; '
            '<span style="color:#0d6efd;">{} In Progress</span> &nbsp;|&nbsp; '
            '<span style="color:#198754;">{} Completed</span>',
            total, active, complete,
        )
    application_count_display.short_description = 'Application Stats'


# Proxy model for separate Commission admin page
class ScholarshipCommission(scholarships):
    class Meta:
        proxy = True
        verbose_name = "Scholarship Commission"
        verbose_name_plural = "Scholarship Commissions"


@admin.register(ScholarshipCommission)
class ScholarshipCommissionAdmin(admin.ModelAdmin):
    """Dedicated admin page for managing Agent & HQ commissions per scholarship"""
    list_display = ['name', 'degree', 'major', 'price_display', 'agent_commission', 'hq_commission', 'total_commission']
    list_editable = ['agent_commission', 'hq_commission']
    list_filter = ['degree', 'scholarship_type']
    search_fields = ['name', 'major']
    list_per_page = 50

    def price_display(self, obj):
        return format_html('<strong>${:,.2f}</strong>', obj.price)
    price_display.short_description = 'Price'

    def agent_commission_display(self, obj):
        return format_html('${:,.2f}', obj.agent_commission)
    agent_commission_display.short_description = 'Agent'

    def hq_commission_display(self, obj):
        return format_html('${:,.2f}', obj.hq_commission)
    hq_commission_display.short_description = 'HQ'

    def total_commission(self, obj):
        total = obj.agent_commission + obj.hq_commission
        return format_html('<strong>${:,.2f}</strong>', total)
    total_commission.short_description = 'Total Commissions'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = 'Manage Agent & HQ Commissions'
        return super().changelist_view(request, extra_context)


# ─── Application Status History Inline ───────────────────────────
class StatusHistoryInline(admin.TabularInline):
    model = ApplicationStatusHistory
    fields = ['old_status', 'new_status', 'changed_by', 'note', 'changed_at']
    readonly_fields = ['old_status', 'new_status', 'changed_by', 'note', 'changed_at']
    extra = 0
    max_num = 0
    verbose_name = 'Status Change'
    verbose_name_plural = 'Status History (Audit Trail)'
    ordering = ['-changed_at']


class AdmissionLetterInline(admin.TabularInline):
    model = AdmissionLetter
    fields = ['file', 'status', 'uploaded_by', 'uploaded_at', 'approved_at']
    readonly_fields = ['uploaded_by', 'uploaded_at', 'approved_at']
    extra = 0
    max_num = 1
    verbose_name = 'Admission Letter'
    verbose_name_plural = 'Admission Letters'


class JW02FormInline(admin.TabularInline):
    model = JW02Form
    fields = ['file', 'status', 'uploaded_by', 'uploaded_at', 'approved_at']
    readonly_fields = ['uploaded_by', 'uploaded_at', 'approved_at']
    extra = 0
    max_num = 1
    verbose_name = 'JW02 Form'
    verbose_name_plural = 'JW02 Forms'


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['app_id', 'student_link', 'scholarship_link', 'office_display', 'status_badge', 'agent_display', 'hq_display', 'applied_date']
    list_filter = ['status', 'office', 'applied_date', 'assigned_agent', 'assigned_hq']
    search_fields = ['app_id', 'user__username', 'user__first_name', 'user__last_name', 'scholarship__name']
    readonly_fields = ['app_id', 'applied_date', 'approved_date', 'completed_date', 'document_checklist']
    raw_id_fields = ['user', 'scholarship', 'assigned_agent', 'assigned_hq', 'office']
    list_per_page = 30
    save_on_top = True
    date_hierarchy = 'applied_date'
    actions = ['mark_as_rejected']

    fieldsets = (
        (None, {
            'fields': ('app_id', 'user', 'scholarship', 'office', 'status'),
            'description': (
                '<strong>📄 Application Overview</strong><br>'
                'Core application data. The <strong>office</strong> is auto-assigned when the application is created. '
                'Status changes should normally happen through the portal workflows, not here.'
            ),
        }),
        ('🧑‍💼 Assignment', {
            'fields': ('assigned_agent', 'assigned_hq', 'deadline'),
            'description': (
                '<strong>Agent</strong> is assigned by the office after payment verification.<br>'
                '<strong>HQ</strong> is assigned by the agent after approval.<br>'
                '<strong>Deadline</strong> is the date by which HQ should submit to the university.'
            ),
        }),
        ('📎 Documents', {
            'fields': ('document_checklist', 'passport', 'photo', 'graduation_certificate', 'criminal_record',
                       'medical_examination', 'letter_of_recommendation_1', 'letter_of_recommendation_2',
                       'study_plan', 'english_certificate'),
            'description': 'Uploaded application documents. Each file is validated for size (5MB max) and type (PDF, JPG, PNG).',
            'classes': ('collapse',),
        }),
        ('⚠️ Rejection', {
            'fields': ('rejection_reason',),
            'classes': ('collapse',),
        }),
        ('📅 Dates', {
            'fields': ('applied_date', 'approved_date', 'completed_date'),
            'classes': ('collapse',),
        }),
    )

    inlines = [AdmissionLetterInline, JW02FormInline, StatusHistoryInline]

    def student_link(self, obj):
        return format_html('<a href="/admin/users/user/{}/change/">{}</a>', obj.user.pk, obj.user.get_full_name() or obj.user.username)
    student_link.short_description = 'Student'

    def scholarship_link(self, obj):
        return format_html('<a href="/admin/scholarships/scholarships/{}/change/">{}</a>', obj.scholarship.pk, obj.scholarship.name)
    scholarship_link.short_description = 'Scholarship'

    def office_display(self, obj):
        if obj.office:
            return format_html('<a href="/admin/office/office/{}/change/">{}</a>', obj.office.pk, obj.office.name)
        return format_html('<span style="color:#dc3545;">⚠ None</span>')
    office_display.short_description = 'Office'

    STATUS_COLORS = {
        'draft': '#6c757d', 'submitted': '#0dcaf0', 'under_review': '#fd7e14',
        'documents_verified': '#20c997', 'payment_verified': '#0d6efd',
        'approved': '#198754', 'rejected': '#dc3545', 'in_progress': '#6610f2',
        'admission_letter_uploaded': '#d63384', 'admission_letter_approved': '#198754',
        'jw02_uploaded': '#d63384', 'jw02_approved': '#198754',
        'letter_pending': '#ffc107', 'jw02_pending': '#ffc107', 'complete': '#198754',
    }

    def status_badge(self, obj):
        color = self.STATUS_COLORS.get(obj.status, '#6c757d')
        text_color = '#000' if obj.status in ('letter_pending', 'jw02_pending') else '#fff'
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;border-radius:10px;font-size:11px;white-space:nowrap;">{}</span>',
            color, text_color, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def agent_display(self, obj):
        if obj.assigned_agent:
            return obj.assigned_agent.get_full_name() or obj.assigned_agent.username
        return '—'
    agent_display.short_description = 'Agent'

    def hq_display(self, obj):
        if obj.assigned_hq:
            return obj.assigned_hq.get_full_name() or obj.assigned_hq.username
        return '—'
    hq_display.short_description = 'HQ'

    def document_checklist(self, obj):
        docs = [
            ('Passport', obj.passport),
            ('Photo', obj.photo),
            ('Graduation Cert.', obj.graduation_certificate),
            ('Criminal Record', obj.criminal_record),
            ('Medical Exam', obj.medical_examination),
            ('Recommendation 1', obj.letter_of_recommendation_1),
            ('Recommendation 2', obj.letter_of_recommendation_2),
            ('Study Plan', obj.study_plan),
            ('English Cert.', obj.english_certificate),
        ]
        items = []
        for label, field in docs:
            if field:
                items.append(format_html('<span style="color:#198754;">✓</span> {}', label))
            else:
                items.append(format_html('<span style="color:#dc3545;">✗</span> {}', label))
        return format_html('<br>'.join(items))
    document_checklist.short_description = 'Document Status'

    @admin.action(description='Mark selected as Rejected')
    def mark_as_rejected(self, request, queryset):
        count = queryset.exclude(status__in=['complete', 'rejected']).update(status='rejected')
        self.message_user(request, f'{count} application(s) marked as rejected.')


@admin.register(AdmissionLetter)
class AdmissionLetterAdmin(admin.ModelAdmin):
    list_display = ['application', 'uploaded_by', 'status_badge', 'uploaded_at', 'approved_at']
    list_filter = ['status', 'uploaded_at']
    search_fields = ['application__user__username', 'application__app_id']
    readonly_fields = ['uploaded_at', 'approved_at']
    list_per_page = 25

    fieldsets = (
        (None, {
            'fields': ('application', 'file', 'status', 'uploaded_by'),
            'description': 'Admission letters uploaded by HQ. The agent reviews and approves/requests revision.',
        }),
        ('Review', {
            'fields': ('revision_note', 'approved_by', 'approved_at'),
        }),
        ('Metadata', {
            'fields': ('uploaded_at',),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {'pending_verification': '#fd7e14', 'approved': '#198754', 'revision_requested': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'


@admin.register(JW02Form)
class JW02FormAdmin(admin.ModelAdmin):
    list_display = ['application', 'uploaded_by', 'status_badge', 'uploaded_at', 'approved_at']
    list_filter = ['status', 'uploaded_at']
    search_fields = ['application__user__username', 'application__app_id']
    readonly_fields = ['uploaded_at', 'approved_at']
    list_per_page = 25

    fieldsets = (
        (None, {
            'fields': ('application', 'file', 'status', 'uploaded_by'),
            'description': 'JW02 forms uploaded by HQ. The agent reviews and approves/requests revision.',
        }),
        ('Review', {
            'fields': ('revision_note', 'approved_by', 'approved_at'),
        }),
        ('Metadata', {
            'fields': ('uploaded_at',),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {'pending_verification': '#fd7e14', 'approved': '#198754', 'revision_requested': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'


@admin.register(ApplicationStatusHistory)
class ApplicationStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['application', 'old_status', 'arrow', 'new_status', 'changed_by', 'note_preview', 'changed_at']
    list_filter = ['new_status', 'changed_at']
    search_fields = ['application__user__username', 'application__app_id', 'note']
    readonly_fields = ['application', 'old_status', 'new_status', 'changed_by', 'note', 'changed_at']
    list_per_page = 50
    date_hierarchy = 'changed_at'

    fieldsets = (
        (None, {
            'fields': ('application', 'old_status', 'new_status', 'changed_by', 'note', 'changed_at'),
            'description': (
                'Complete audit trail of every status transition. '
                'This log is read-only and cannot be modified or deleted.'
            ),
        }),
    )

    def arrow(self, obj):
        return format_html('<span style="color:#6c757d;">→</span>')
    arrow.short_description = ''

    def note_preview(self, obj):
        if obj.note:
            return obj.note[:60] + '…' if len(obj.note) > 60 else obj.note
        return '—'
    note_preview.short_description = 'Note'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False