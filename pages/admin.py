from django.contrib import admin
from django.utils.html import format_html
from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """
    Singleton admin — users can only edit the one existing record.
    The "Add" button is hidden and deletion is disabled.
    """

    fieldsets = (
        ('Branding', {
            'fields': ('site_name', 'tagline', 'logo', 'logo_preview', 'favicon'),
            'description': 'Site name, tagline, and logo displayed across the website.',
        }),
        ('SEO / Meta Tags', {
            'fields': ('meta_description', 'meta_keywords', 'og_image'),
            'description': 'Search engine optimization settings. These appear in search results and social media previews.',
        }),
        ('Contact Information', {
            'fields': ('contact_email', 'contact_phone', 'address'),
        }),
        ('Social Media Links', {
            'fields': ('facebook_url', 'instagram_url', 'twitter_url', 'linkedin_url', 'youtube_url', 'whatsapp_number'),
            'classes': ('collapse',),
        }),
        ('Analytics', {
            'fields': ('google_analytics_id',),
            'classes': ('collapse',),
        }),
        ('Footer', {
            'fields': ('footer_text',),
        }),
    )

    readonly_fields = ['logo_preview']

    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-height:60px; max-width:200px; border:1px solid #ddd; padding:4px; border-radius:4px;" />',
                obj.logo.url,
            )
        return '(No logo uploaded)'
    logo_preview.short_description = 'Current Logo'

    def has_add_permission(self, request):
        # Only allow adding if no instance exists yet
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """Redirect the list view straight to the edit form (singleton UX)."""
        obj = SiteSettings.load()
        from django.shortcuts import redirect
        return redirect(f'/admin/pages/sitesettings/{obj.pk}/change/')


# Customize the admin site header
admin.site.site_header = 'EDU System Administration'
admin.site.site_title = 'EDU Admin'
admin.site.index_title = 'Administration Dashboard'
