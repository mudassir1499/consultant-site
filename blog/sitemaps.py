from django.contrib.sitemaps import Sitemap
from .models import Post


class BlogPostSitemap(Sitemap):
    """Sitemap for published blog posts."""
    changefreq = 'weekly'
    priority = 0.7
    protocol = 'https'

    def items(self):
        return Post.objects.filter(status='published').order_by('-published_date')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()
