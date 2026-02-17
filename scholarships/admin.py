from django.contrib import admin
from .models import scholarships, Application, AdmissionLetter, JW02Form, ApplicationStatusHistory


@admin.register(scholarships)
class ScholarshipsAdmin(admin.ModelAdmin):
    list_display = ['name', 'degree', 'scholarship_type', 'deadline', 'price']
    list_filter = ['degree', 'scholarship_type', 'semester']
    search_fields = ['name', 'major', 'city']
    readonly_fields = ['id']


# Proxy model for separate Commission admin page
class ScholarshipCommission(scholarships):
    class Meta:
        proxy = True
        verbose_name = "Scholarship Commission"
        verbose_name_plural = "Scholarship Commissions"


@admin.register(ScholarshipCommission)
class ScholarshipCommissionAdmin(admin.ModelAdmin):
    """Dedicated admin page for managing Agent & HQ commissions per scholarship"""
    list_display = ['name', 'degree', 'major', 'price', 'agent_commission', 'hq_commission']
    list_editable = ['agent_commission', 'hq_commission']
    list_filter = ['degree', 'scholarship_type']
    search_fields = ['name', 'major']
    list_per_page = 50

    def has_add_permission(self, request):
        return False  # Scholarships are added via the main admin

    def has_delete_permission(self, request, obj=None):
        return False  # Commissions page is edit-only


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['app_id', 'user', 'scholarship', 'status', 'assigned_agent', 'assigned_hq', 'applied_date']
    list_filter = ['status', 'applied_date']
    search_fields = ['user__username', 'scholarship__name']
    readonly_fields = ['applied_date', 'approved_date', 'completed_date']
    raw_id_fields = ['user', 'scholarship', 'assigned_agent', 'assigned_hq']


@admin.register(AdmissionLetter)
class AdmissionLetterAdmin(admin.ModelAdmin):
    list_display = ['application', 'uploaded_by', 'status', 'uploaded_at', 'approved_at']
    list_filter = ['status', 'uploaded_at']
    search_fields = ['application__user__username']
    readonly_fields = ['uploaded_at', 'approved_at']


@admin.register(JW02Form)
class JW02FormAdmin(admin.ModelAdmin):
    list_display = ['application', 'uploaded_by', 'status', 'uploaded_at', 'approved_at']
    list_filter = ['status', 'uploaded_at']
    search_fields = ['application__user__username']
    readonly_fields = ['uploaded_at', 'approved_at']


@admin.register(ApplicationStatusHistory)
class ApplicationStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['application', 'old_status', 'new_status', 'changed_by', 'changed_at']
    list_filter = ['new_status', 'changed_at']
    search_fields = ['application__user__username']
    readonly_fields = ['application', 'old_status', 'new_status', 'changed_by', 'note', 'changed_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False