from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.post_list, name='post_list'),
    path('category/<slug:slug>/', views.category_posts, name='category_posts'),
    path('<slug:slug>/', views.post_detail, name='post_detail'),
]
