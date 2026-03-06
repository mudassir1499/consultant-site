"""
DevTools Middleware — Logs requests and tracks DB query counts.
Uses an in-memory deque buffer for recent request history.
"""
import time
import logging
from collections import deque
from threading import Lock
from django.conf import settings
from django.db import connection

logger = logging.getLogger('devtools.requests')

# In-memory ring buffer for recent requests (thread-safe)
_request_log = deque(maxlen=500)
_lock = Lock()


def get_recent_requests():
    """Return list of recent request dicts (newest first)."""
    with _lock:
        return list(reversed(_request_log))


class DevToolsRequestMiddleware:
    """
    Middleware that logs every request with timing and query count.
    Only active when DEVTOOLS_ENABLED is True.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'DEVTOOLS_ENABLED', False)
        self.log_requests = getattr(settings, 'DEVTOOLS_LOG_REQUESTS', True)

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        # Skip static/media
        path = request.path
        if path.startswith(('/static/', '/media/', '/favicon.ico')):
            return self.get_response(request)

        start_time = time.time()
        initial_queries = len(connection.queries) if settings.DEBUG else 0

        response = self.get_response(request)

        duration = (time.time() - start_time) * 1000  # ms
        query_count = len(connection.queries) - initial_queries if settings.DEBUG else 0
        status_code = response.status_code

        entry = {
            'method': request.method,
            'path': path,
            'status': status_code,
            'duration_ms': round(duration, 1),
            'query_count': query_count,
            'user': str(request.user) if hasattr(request, 'user') else 'Anonymous',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'ip': request.META.get('REMOTE_ADDR', ''),
        }

        with _lock:
            _request_log.append(entry)

        if self.log_requests:
            logger.info(
                '%s %s %d %.1fms %dQ [%s]',
                request.method, path, status_code,
                duration, query_count, entry['user']
            )

        return response
