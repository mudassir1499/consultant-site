"""
DevTools Views — Debug portal for superusers.
Provides error logs, request logs, submission tracker, and health stats.
"""
import os
import sys
import json
import platform
from collections import Counter
from datetime import timedelta

import django
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.db import connection
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from scholarships.models import Application
from users.models import User


def is_superuser(user):
    return user.is_authenticated and user.is_superuser


def _read_log_lines(log_path, max_lines=200, level_filter=None):
    """Read last N lines from a log file, optionally filtering by level."""
    lines = []
    try:
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
            if level_filter:
                all_lines = [l for l in all_lines if level_filter.upper() in l]
            lines = all_lines[-max_lines:]
    except Exception:
        pass
    return lines


@user_passes_test(is_superuser)
def dashboard(request):
    """Main devtools dashboard with overview stats."""
    from finance.models import application_payment

    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)

    # Application stats
    total_apps = Application.objects.count()
    apps_today = Application.objects.filter(applied_date=today).count()
    apps_this_week = Application.objects.filter(applied_date__gte=week_ago).count()

    # Status breakdown
    status_counts = dict(
        Application.objects.values_list('status')
        .annotate(c=Count('status'))
        .values_list('status', 'c')
    )

    # User stats
    total_users = User.objects.count()
    users_by_role = dict(
        User.objects.values_list('role')
        .annotate(c=Count('role'))
        .values_list('role', 'c')
    )

    # Payment stats
    total_payments = application_payment.objects.count()
    payment_status_counts = dict(
        application_payment.objects.values_list('payment_status')
        .annotate(c=Count('payment_status'))
        .values_list('payment_status', 'c')
    )

    # Log file sizes
    log_dir = settings.BASE_DIR / 'logs'
    log_files = {}
    if log_dir.exists():
        for f in log_dir.iterdir():
            if f.is_file():
                log_files[f.name] = {
                    'size': f.stat().st_size,
                    'size_display': _format_size(f.stat().st_size),
                    'modified': f.stat().st_mtime,
                }

    # Recent request stats from middleware buffer
    from devtools.middleware import get_recent_requests
    recent_requests = get_recent_requests()
    error_requests = [r for r in recent_requests if r['status'] >= 400]
    slow_requests = [r for r in recent_requests if r['duration_ms'] > 500]

    context = {
        'total_apps': total_apps,
        'apps_today': apps_today,
        'apps_this_week': apps_this_week,
        'status_counts': status_counts,
        'total_users': total_users,
        'users_by_role': users_by_role,
        'total_payments': total_payments,
        'payment_status_counts': payment_status_counts,
        'log_files': log_files,
        'total_requests': len(recent_requests),
        'error_requests': len(error_requests),
        'slow_requests': len(slow_requests),
        'python_version': sys.version,
        'django_version': django.get_version(),
        'debug_mode': settings.DEBUG,
        'database_engine': settings.DATABASES['default']['ENGINE'],
    }
    return render(request, 'devtools/dashboard.html', context)


@user_passes_test(is_superuser)
def log_viewer(request):
    """View application logs with level filtering."""
    log_dir = settings.BASE_DIR / 'logs'
    log_file = request.GET.get('file', 'app.log')
    level = request.GET.get('level', '')
    max_lines = int(request.GET.get('lines', 200))

    # Security: prevent directory traversal
    safe_name = os.path.basename(log_file)
    log_path = log_dir / safe_name

    lines = _read_log_lines(log_path, max_lines, level or None)

    # List available log files
    available_files = []
    if log_dir.exists():
        available_files = sorted([f.name for f in log_dir.iterdir() if f.is_file()])

    context = {
        'lines': lines,
        'log_file': safe_name,
        'level': level,
        'max_lines': max_lines,
        'available_files': available_files,
    }
    return render(request, 'devtools/log_viewer.html', context)


@user_passes_test(is_superuser)
def request_log(request):
    """View recent HTTP request log from middleware buffer."""
    from devtools.middleware import get_recent_requests
    recent = get_recent_requests()

    status_filter = request.GET.get('status', '')
    method_filter = request.GET.get('method', '')

    if status_filter:
        recent = [r for r in recent if str(r['status']).startswith(status_filter)]
    if method_filter:
        recent = [r for r in recent if r['method'] == method_filter.upper()]

    context = {
        'requests': recent[:200],
        'status_filter': status_filter,
        'method_filter': method_filter,
    }
    return render(request, 'devtools/request_log.html', context)


@user_passes_test(is_superuser)
def submission_tracker(request):
    """Track application submissions and their current processing state."""
    now = timezone.now()
    days = int(request.GET.get('days', 7))
    since = now - timedelta(days=days)

    recent_apps = Application.objects.filter(
        applied_date__gte=since
    ).select_related('user', 'scholarship', 'office', 'assigned_agent', 'assigned_hq').order_by('-applied_date')

    # Daily submission counts
    daily_counts = {}
    for app in recent_apps:
        day = app.applied_date.strftime('%Y-%m-%d') if app.applied_date else 'Unknown'
        daily_counts[day] = daily_counts.get(day, 0) + 1

    # Status pipeline
    pipeline = Counter()
    for app in recent_apps:
        pipeline[app.status] += 1

    # Stuck applications (no status change in 3+ days)
    from scholarships.models import ApplicationStatusHistory
    stuck = []
    for app in recent_apps:
        last_change = ApplicationStatusHistory.objects.filter(
            application=app
        ).order_by('-changed_at').first()
        if last_change and (now - last_change.changed_at).days >= 3:
            stuck.append({
                'app': app,
                'days_stuck': (now - last_change.changed_at).days,
                'last_status_change': last_change.changed_at,
            })

    context = {
        'recent_apps': recent_apps,
        'daily_counts': dict(sorted(daily_counts.items())),
        'pipeline': dict(pipeline.most_common()),
        'stuck_apps': stuck,
        'days': days,
        'total_recent': recent_apps.count(),
    }
    return render(request, 'devtools/submission_tracker.html', context)


@user_passes_test(is_superuser)
def health_check(request):
    """System health check page."""
    checks = {}

    # Database
    try:
        connection.ensure_connection()
        checks['database'] = {'status': 'ok', 'detail': settings.DATABASES['default']['ENGINE']}
    except Exception as e:
        checks['database'] = {'status': 'error', 'detail': str(e)}

    # Log directory
    log_dir = settings.BASE_DIR / 'logs'
    if log_dir.exists() and os.access(log_dir, os.W_OK):
        checks['log_directory'] = {'status': 'ok', 'detail': str(log_dir)}
    else:
        checks['log_directory'] = {'status': 'error', 'detail': 'Not writable or missing'}

    # Media directory
    media_root = settings.MEDIA_ROOT
    if os.path.exists(media_root) and os.access(media_root, os.W_OK):
        checks['media_directory'] = {'status': 'ok', 'detail': str(media_root)}
    else:
        checks['media_directory'] = {'status': 'warning', 'detail': 'Not writable or missing'}

    # Disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage(settings.BASE_DIR)
        checks['disk_space'] = {
            'status': 'ok' if free > 100 * 1024 * 1024 else 'warning',
            'detail': f'{_format_size(free)} free of {_format_size(total)}'
        }
    except Exception:
        checks['disk_space'] = {'status': 'unknown', 'detail': 'Could not check'}

    # Python & Django
    checks['python'] = {'status': 'ok', 'detail': sys.version.split()[0]}
    checks['django'] = {'status': 'ok', 'detail': django.get_version()}
    checks['platform'] = {'status': 'ok', 'detail': platform.platform()}
    checks['debug_mode'] = {
        'status': 'warning' if settings.DEBUG else 'ok',
        'detail': 'ON' if settings.DEBUG else 'OFF'
    }

    context = {
        'checks': checks,
        'all_ok': all(c['status'] == 'ok' for c in checks.values()),
    }
    return render(request, 'devtools/health_check.html', context)


# ─── API Endpoints ───────────────────────────────────────────────────
@user_passes_test(is_superuser)
def api_logs(request):
    """API: Return log lines as JSON."""
    log_dir = settings.BASE_DIR / 'logs'
    log_file = request.GET.get('file', 'app.log')
    level = request.GET.get('level', '')
    max_lines = int(request.GET.get('lines', 100))

    safe_name = os.path.basename(log_file)
    lines = _read_log_lines(log_dir / safe_name, max_lines, level or None)
    return JsonResponse({'lines': [l.rstrip() for l in lines], 'file': safe_name})


@user_passes_test(is_superuser)
def api_requests(request):
    """API: Return recent requests as JSON."""
    from devtools.middleware import get_recent_requests
    recent = get_recent_requests()[:100]
    return JsonResponse({'requests': recent})


@user_passes_test(is_superuser)
def api_health(request):
    """API: Quick health check as JSON."""
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    return JsonResponse({
        'database': db_ok,
        'debug': settings.DEBUG,
        'python': sys.version.split()[0],
        'django': django.get_version(),
    })


def _format_size(size_bytes):
    """Format bytes as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(size_bytes) < 1024:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024
    return f'{size_bytes:.1f} TB'
