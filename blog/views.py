from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Post, Category


def post_list(request):
    """Blog listing page with search and category filter."""
    posts = Post.objects.filter(status='published').select_related('category', 'author')
    categories = Category.objects.all()

    # Search
    query = request.GET.get('q', '').strip()
    if query:
        posts = posts.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(excerpt__icontains=query)
        )

    # Category filter
    category_slug = request.GET.get('category', '')
    active_category = None
    if category_slug:
        active_category = get_object_or_404(Category, slug=category_slug)
        posts = posts.filter(category=active_category)

    # Pagination
    paginator = Paginator(posts, 9)
    page = request.GET.get('page')
    posts = paginator.get_page(page)

    # Featured post (latest)
    featured = Post.objects.filter(status='published').first()

    return render(request, 'blog/post_list.html', {
        'posts': posts,
        'categories': categories,
        'featured': featured if not query and not category_slug and (not page or page == '1') else None,
        'query': query,
        'active_category': active_category,
    })


def post_detail(request, slug):
    """Individual blog post page."""
    post = get_object_or_404(Post, slug=slug, status='published')

    # Increment view count
    Post.objects.filter(pk=post.pk).update(views_count=post.views_count + 1)

    # Related posts (same category, exclude current)
    related_posts = Post.objects.filter(
        status='published', category=post.category
    ).exclude(pk=post.pk)[:3] if post.category else Post.objects.filter(
        status='published'
    ).exclude(pk=post.pk)[:3]

    # All categories for sidebar
    categories = Category.objects.all()

    return render(request, 'blog/post_detail.html', {
        'post': post,
        'related_posts': related_posts,
        'categories': categories,
    })


def category_posts(request, slug):
    """Posts filtered by category."""
    category = get_object_or_404(Category, slug=slug)
    posts = Post.objects.filter(status='published', category=category).select_related('author')

    paginator = Paginator(posts, 9)
    page = request.GET.get('page')
    posts = paginator.get_page(page)

    categories = Category.objects.all()

    return render(request, 'blog/post_list.html', {
        'posts': posts,
        'categories': categories,
        'active_category': category,
        'query': '',
        'featured': None,
    })
