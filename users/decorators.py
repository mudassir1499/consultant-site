"""
Shared decorators for role-based access control.
"""

from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required


def role_required(*roles, login_url_override=None):
    """
    Decorator that checks if the logged-in user has one of the specified roles.
    Usage: @role_required('agent') or @role_required('agent', 'headquarters')
    Usage with custom login: @role_required('agent', login_url_override='agent:login')
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required(login_url=login_url_override or 'users:login')
        def wrapper(request, *args, **kwargs):
            if request.user.role in roles:
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("You do not have permission to access this page.")
        return wrapper
    return decorator
