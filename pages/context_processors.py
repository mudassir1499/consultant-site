from .models import SiteSettings


def site_settings(request):
    """Make SiteSettings available in all templates as {{ site_settings }}."""
    try:
        settings = SiteSettings.load()
    except Exception:
        settings = None
    return {'site_settings': settings}
