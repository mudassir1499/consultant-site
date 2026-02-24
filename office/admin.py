from django.contrib import admin
from django.utils.html import format_html
from .models import Office, OfficeRegion


class OfficeRegionInline(admin.TabularInline):
    """Inline for managing country/city → office mappings"""
    model = OfficeRegion
    extra = 1
    fields = ['country_name', 'country_code', 'city']
    verbose_name = 'Region Mapping'
    verbose_name_plural = 'Region Mappings (Country → Office Routing)'


class StaffInline(admin.TabularInline):
    """Inline showing staff members assigned to this office"""
    from users.models import User
    model = User
    fk_name = 'office'
    fields = ['username', 'first_name', 'last_name', 'role', 'email', 'status']
    readonly_fields = ['username', 'first_name', 'last_name', 'email']
    extra = 0
    verbose_name = 'Staff Member'
    verbose_name_plural = 'Assigned Staff & Agents'
    can_delete = False
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).filter(role__in=['office', 'agent'])

    def has_add_permission(self, request, obj=None):
        return False  # Staff are assigned via the User admin


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'city', 'country', 'phone_display', 'email', 'is_active', 'is_default', 'staff_count', 'application_count']
    list_filter = ['is_active', 'is_default', 'country']
    search_fields = ['name', 'code', 'city', 'country']
    list_editable = ['is_active', 'is_default']
    prepopulated_fields = {'code': ('name',)}
    readonly_fields = ['created_at', 'staff_count_display', 'application_count_display', 'region_summary']
    list_per_page = 25
    save_on_top = True

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'is_active', 'is_default'),
            'description': (
                '<strong>📋 Office Setup</strong><br>'
                'Each office represents a physical branch location. '
                'The <strong>code</strong> is a short unique identifier (auto-generated from name). '
                'Mark one office as <strong>Default</strong> — it receives students from unmapped regions.'
            ),
        }),
        ('📍 Location', {
            'fields': ('city', 'country', 'address'),
            'description': 'Physical location of this branch office.',
        }),
        ('📞 Contact', {
            'fields': ('phone', 'email'),
            'description': 'Contact details shown to staff for this branch.',
        }),
        ('📊 Statistics', {
            'fields': ('staff_count_display', 'application_count_display', 'region_summary'),
            'description': 'Read-only overview of this office\'s data.',
        }),
        ('🕐 Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    inlines = [OfficeRegionInline, StaffInline]

    def staff_count(self, obj):
        count = obj.staff.filter(role__in=['office', 'agent']).count()
        return count
    staff_count.short_description = 'Staff'
    staff_count.admin_order_field = 'staff_count'

    def application_count(self, obj):
        return obj.applications.count()
    application_count.short_description = 'Apps'

    def staff_count_display(self, obj):
        office_staff = obj.staff.filter(role='office').count()
        agents = obj.staff.filter(role='agent').count()
        return format_html(
            '<span style="font-size:1.1em;"><strong>{}</strong> Office Workers &nbsp;|&nbsp; <strong>{}</strong> Agents</span>',
            office_staff, agents,
        )
    staff_count_display.short_description = 'Staff Breakdown'

    def application_count_display(self, obj):
        from scholarships.models import Application
        total = obj.applications.count()
        active = obj.applications.exclude(status__in=['complete', 'rejected']).count()
        complete = obj.applications.filter(status='complete').count()
        return format_html(
            '<span style="font-size:1.1em;"><strong>{}</strong> Total &nbsp;|&nbsp; '
            '<span style="color:#198754;">{} Active</span> &nbsp;|&nbsp; '
            '<span style="color:#6c757d;">{} Completed</span></span>',
            total, active, complete,
        )
    application_count_display.short_description = 'Applications Summary'

    def region_summary(self, obj):
        regions = obj.regions.all()
        if not regions:
            return format_html('<em style="color:#999;">No region mappings — add them below.</em>')
        items = ', '.join(
            f'{r.country_name}' + (f' ({r.city})' if r.city else '') for r in regions[:10]
        )
        if regions.count() > 10:
            items += f' … and {regions.count() - 10} more'
        return items
    region_summary.short_description = 'Mapped Regions'

    def phone_display(self, obj):
        return obj.phone or '—'
    phone_display.short_description = 'Phone'

    def is_default_badge(self, obj):
        if obj.is_default:
            return format_html('<span style="background:#0d6efd;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">Default</span>')
        return ''
    is_default_badge.short_description = 'Default'

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="background:#198754;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">Active</span>')
        return format_html('<span style="background:#dc3545;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">Inactive</span>')
    is_active_badge.short_description = 'Status'

    class Media:
        css = {'all': ('admin/css/custom_admin.css',)}


@admin.register(OfficeRegion)
class OfficeRegionAdmin(admin.ModelAdmin):
    """
    Manage which countries/cities are routed to which office.
    When a student registers with a location, the system auto-assigns them to the matching office.
    """
    list_display = ['country_name', 'country_code', 'city', 'office', 'office_active']
    list_filter = ['office', 'country_name']
    search_fields = ['country_name', 'country_code', 'city']
    list_editable = ['office']
    raw_id_fields = ['office']
    list_per_page = 50

    fieldsets = (
        (None, {
            'fields': ('office', 'country_name', 'country_code', 'city'),
            'description': (
                '<strong>🌍 Region Routing</strong><br>'
                'Map a country (and optionally a city) to an office branch. '
                'When a student registers with this country/city, they are <strong>automatically assigned</strong> to the mapped office.<br>'
                '<em>Leave city blank to route the entire country to one office.</em>'
            ),
        }),
    )

    def office_active(self, obj):
        if obj.office.is_active:
            return format_html('<span style="color:#198754;">✓ Active</span>')
        return format_html('<span style="color:#dc3545;">✗ Inactive</span>')
    office_active.short_description = 'Office Status'
