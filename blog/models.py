from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings


class Category(models.Model):
    """Blog post categories for organizing content."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50, blank=True, default='bi-folder',
        help_text='Bootstrap icon class, e.g. bi-mortarboard'
    )
    order = models.PositiveIntegerField(default=0, help_text='Display order (lower = first)')

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:category_posts', kwargs={'slug': self.slug})

    @property
    def published_post_count(self):
        return self.posts.filter(status='published').count()


class Post(models.Model):
    """Blog post for SEO content marketing."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]

    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=270, unique=True, blank=True)
    content = models.TextField(help_text='Full article content (HTML allowed)')
    excerpt = models.TextField(
        max_length=500, blank=True,
        help_text='Short summary shown in post cards (auto-generated if empty)'
    )
    featured_image = models.ImageField(
        upload_to='blog/featured/', blank=True, null=True,
        help_text='Recommended size: 1200x630px for social sharing'
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='posts'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='blog_posts'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    published_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # SEO fields
    meta_title = models.CharField(
        max_length=70, blank=True,
        help_text='Custom SEO title (defaults to post title if empty)'
    )
    meta_description = models.CharField(
        max_length=160, blank=True,
        help_text='SEO description for search engines'
    )
    meta_keywords = models.CharField(
        max_length=255, blank=True,
        help_text='Comma-separated keywords'
    )

    # Engagement
    views_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ['-published_date', '-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.status == 'published' and not self.published_date:
            self.published_date = timezone.now()
        if not self.excerpt and self.content:
            import re
            clean = re.sub(r'<[^>]+>', '', self.content)
            self.excerpt = clean[:300].rsplit(' ', 1)[0] + '...' if len(clean) > 300 else clean
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:post_detail', kwargs={'slug': self.slug})

    @property
    def reading_time(self):
        """Estimated reading time in minutes."""
        import re
        word_count = len(re.sub(r'<[^>]+>', '', self.content).split())
        return max(1, round(word_count / 200))

    @property
    def seo_title(self):
        return self.meta_title or self.title

    @property
    def seo_description(self):
        return self.meta_description or self.excerpt[:160]
