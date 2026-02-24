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
        ('🏢 Branding', {
            'fields': ('site_name', 'tagline', 'logo', 'logo_preview', 'favicon'),
            'description': (
                '<strong>Site Identity</strong><br>'
                'These values appear in the header, browser tab, and throughout the website.<br>'
                '• <strong>Logo:</strong> Recommended size 200×60 px, PNG with transparent background.<br>'
                '• <strong>Favicon:</strong> 32×32 px .ico or .png file.'
            ),
        }),
        ('🔍 SEO / Meta Tags', {
            'fields': ('meta_description', 'meta_keywords', 'og_image'),
            'description': (
                'Search engine optimization settings. These appear in Google search results and when '
                'the site is shared on social media.<br>'
                '• <strong>Meta Description:</strong> Keep under 160 characters for best results.<br>'
                '• <strong>OG Image:</strong> 1200×630 px recommended for social media previews.'
            ),
        }),
        ('📞 Contact Information', {
            'fields': ('contact_email', 'contact_phone', 'address'),
            'description': 'Displayed in the footer, contact page, and in automated emails.',
        }),
        ('🌐 Social Media Links', {
            'fields': ('facebook_url', 'instagram_url', 'twitter_url', 'linkedin_url', 'youtube_url', 'whatsapp_number'),
            'classes': ('collapse',),
            'description': (
                'Social media links shown in the website footer. '
                'Leave blank to hide a particular icon. '
                'Use full URLs (e.g., https://facebook.com/yourpage).'
            ),
        }),
        ('📊 Analytics', {
            'fields': ('google_analytics_id',),
            'classes': ('collapse',),
            'description': 'Enter your Google Analytics Measurement ID (e.g., G-XXXXXXXXXX) to enable tracking.',
        }),
        ('📝 Footer', {
            'fields': ('footer_text',),
            'description': 'Custom text displayed at the bottom of every page (e.g., copyright notice).',
        }),
    )

    readonly_fields = ['logo_preview']
    save_on_top = True

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

    class Media:
        css = {'all': ('admin/css/custom_admin.css',)}


# ─── Admin site customization ───────────────────────────────
admin.site.site_header = 'DFS Education — Administration'
admin.site.site_title = 'DFS Admin'
admin.site.index_title = 'Welcome to the DFS Education Admin Panel'
