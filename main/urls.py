"""
URL configuration for main project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from pages.sitemaps import StaticViewSitemap, ScholarshipSitemap
from blog.sitemaps import BlogPostSitemap

sitemaps = {
    'static': StaticViewSitemap,
    'scholarships': ScholarshipSitemap,
    'blog': BlogPostSitemap,
}

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),  # set_language view
    path('admin/', admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('', include('pages.urls')),
    path('users/', include('users.urls')),
    path('scholarships/', include('scholarships.urls')),
    path('finance/', include('finance.urls')),
    path('office/', include('office.urls')),
    path('agent/', include('agent.urls')),
    path('hq/', include('headquarters.urls')),
    path('devtools/', include('devtools.urls')),
    path('blog/', include('blog.urls')),
    path('admin-portal/', include('admin_portal.urls')),
]

# Serve media & static files
# In production on cPanel, Apache serves these via symlinks,
# but this ensures they work in development and as a fallback.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
