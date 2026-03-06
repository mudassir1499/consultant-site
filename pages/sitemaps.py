from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from scholarships.models import scholarships


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages (home, about, contact, scholarship list)."""
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return ['pages:home', 'pages:about', 'pages:contact', 'scholarships:scholarship_list']

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        if item == 'pages:home':
            return 1.0
        if item == 'scholarships:scholarship_list':
            return 0.9
        return 0.7


class ScholarshipSitemap(Sitemap):
    """Sitemap for individual scholarship detail pages."""
    changefreq = 'daily'
    priority = 0.9
    protocol = 'https'

    def items(self):
        return scholarships.objects.order_by('-id')

    def lastmod(self, obj):
        return obj.deadline

    def location(self, obj):
        return obj.get_absolute_url()
