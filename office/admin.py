from django.contrib import admin
from .models import Office, OfficeRegion


class OfficeRegionInline(admin.TabularInline):
    """Inline for managing country/city → office mappings"""
    model = OfficeRegion
    extra = 1
    fields = ['country_name', 'country_code', 'city']


class StaffInline(admin.TabularInline):
    """Inline showing staff members assigned to this office"""
    from users.models import User
    model = User
    fk_name = 'office'
    fields = ['username', 'first_name', 'last_name', 'role', 'email', 'status']
    readonly_fields = ['username', 'first_name', 'last_name', 'email']
    extra = 0
    verbose_name = 'Staff Member'
    verbose_name_plural = 'Staff Members'
    can_delete = False
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).filter(role__in=['office', 'agent'])

    def has_add_permission(self, request, obj=None):
        return False  # Staff are assigned via the User admin


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'city', 'country', 'phone', 'email', 'is_default', 'is_active', 'staff_count', 'application_count']
    list_filter = ['is_active', 'is_default', 'country']
    search_fields = ['name', 'code', 'city', 'country']
    list_editable = ['is_active', 'is_default']
    prepopulated_fields = {'code': ('name',)}
    readonly_fields = ['created_at']

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'is_active', 'is_default'),
        }),
        ('Location', {
            'fields': ('city', 'country', 'address'),
        }),
        ('Contact', {
            'fields': ('phone', 'email'),
        }),
        ('Metadata', {
            'fields': ('created_at',),
        }),
    )

    inlines = [OfficeRegionInline, StaffInline]

    def staff_count(self, obj):
        return obj.staff.filter(role__in=['office', 'agent']).count()
    staff_count.short_description = 'Staff'

    def application_count(self, obj):
        return obj.applications.count()
    application_count.short_description = 'Applications'


@admin.register(OfficeRegion)
class OfficeRegionAdmin(admin.ModelAdmin):
    """Standalone admin for bulk-managing region mappings"""
    list_display = ['country_name', 'country_code', 'city', 'office']
    list_filter = ['office', 'country_name']
    search_fields = ['country_name', 'country_code', 'city']
    list_editable = ['office']
    raw_id_fields = ['office']
