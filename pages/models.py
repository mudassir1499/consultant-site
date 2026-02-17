from django.db import models


class SiteSettings(models.Model):
    """
    Singleton model for site-wide settings managed from the admin panel.
    Only one instance should exist — enforced by the admin and save() override.
    """

    # ─── Branding ────────────────────────────────────────────
    site_name = models.CharField(
        max_length=200, default='Yaamaan Education Consultants',
        help_text='Displayed in the navbar, browser tab title, and footer.',
    )
    tagline = models.CharField(
        max_length=300, blank=True, default='Your Gateway to International Education',
        help_text='Short tagline shown on the home page hero section.',
    )
    logo = models.ImageField(
        upload_to='site/', blank=True, null=True,
        help_text='Site logo (recommended: PNG with transparent background, 200×60px).',
    )
    favicon = models.ImageField(
        upload_to='site/', blank=True, null=True,
        help_text='Browser tab favicon (recommended: 32×32px .ico or .png).',
    )

    # ─── SEO ─────────────────────────────────────────────────
    meta_description = models.CharField(
        max_length=300, blank=True,
        default='Yaamaan Education Consultants - Helping students achieve their dreams of studying abroad.',
        help_text='Meta description for search engines (max 160 chars recommended).',
    )
    meta_keywords = models.CharField(
        max_length=500, blank=True,
        default='education, consultants, study abroad, scholarships, international students',
        help_text='Comma-separated keywords for SEO.',
    )
    og_image = models.ImageField(
        upload_to='site/', blank=True, null=True,
        help_text='Open Graph image for social media sharing (recommended: 1200×630px).',
    )

    # ─── Contact / Footer Info ───────────────────────────────
    contact_email = models.EmailField(
        blank=True, default='info@yaamaan.com',
        help_text='Public contact email displayed on the site.',
    )
    contact_phone = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Public contact phone number.',
    )
    address = models.TextField(
        blank=True, default='',
        help_text='Office address displayed in the footer / contact page.',
    )

    # ─── Social Media ───────────────────────────────────────
    facebook_url = models.URLField(blank=True, default='')
    instagram_url = models.URLField(blank=True, default='')
    twitter_url = models.URLField(blank=True, default='')
    linkedin_url = models.URLField(blank=True, default='')
    youtube_url = models.URLField(blank=True, default='')
    whatsapp_number = models.CharField(
        max_length=30, blank=True, default='',
        help_text='WhatsApp number with country code, e.g. +1234567890',
    )

    # ─── Analytics ───────────────────────────────────────────
    google_analytics_id = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Google Analytics Measurement ID (e.g. G-XXXXXXXXXX).',
    )

    # ─── Footer ──────────────────────────────────────────────
    footer_text = models.CharField(
        max_length=500, blank=True,
        default='© 2024 Yaamaan Education Consultants. All rights reserved.',
        help_text='Custom footer copyright / text.',
    )

    class Meta:
        db_table = 'site_settings'
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of the singleton."""
        pass

    @classmethod
    def load(cls):
        """Get or create the singleton instance."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
