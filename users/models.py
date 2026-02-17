from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]

    # user_id is automatically created by AbstractUser as 'id'
    # email, username, first_name, last_name, date_joined (created_at) are already in AbstractUser
    
    role = models.CharField(max_length=20, choices=[
        ('user', 'User'),
        ('office', 'Office'),
        ('agent', 'Main Agent'),
        ('headquarters', 'Headquarters'),
    ], default='user')
    
    phone = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username

    def is_active_user(self):
        """Check if user account is active"""
        return self.status == 'active'

    class Meta:
        db_table = 'users'


class Notification(models.Model):
    """In-app notification for users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{'[Read]' if self.is_read else '[Unread]'} {self.title} → {self.user.username}"

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
