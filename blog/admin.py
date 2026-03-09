from django.contrib import admin
from .models import Category, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'published_post_count', 'order')
    list_editable = ('order',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

    def published_post_count(self, obj):
        return obj.published_post_count
    published_post_count.short_description = 'Published Posts'


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'author', 'status', 'published_date', 'views_count')
    list_filter = ('status', 'category', 'published_date')
    search_fields = ('title', 'content', 'excerpt')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_date'
    list_editable = ('status',)
    readonly_fields = ('views_count', 'created_at', 'updated_at')
    autocomplete_fields = ('author',)

    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'content', 'excerpt', 'featured_image')
        }),
        ('Organization', {
            'fields': ('category', 'author', 'status', 'published_date')
        }),
        ('SEO', {
            'classes': ('collapse',),
            'fields': ('meta_title', 'meta_description', 'meta_keywords')
        }),
        ('Stats', {
            'classes': ('collapse',),
            'fields': ('views_count', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)
