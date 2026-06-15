from django.conf import settings

def extra_settings(request):
    return {
        'XUI_API_URL': settings.XUI_API_URL,
    }

from accounts.models import AdminSettings

def site_settings(request):
    try:
        settings = AdminSettings.load()
    except Exception:
        settings = None
    return {
        'footer_text': settings.footer_text if settings else 'BETA-build v0.2 by V.',
    }

from accounts.models import Notification

def site_settings(request):
    from accounts.models import AdminSettings
    try:
        settings = AdminSettings.load()
    except Exception:
        settings = None
    return {
        'footer_text': settings.footer_text if settings else 'BETA-build v0.2 by V.',
        'active_notifications': Notification.objects.filter(is_active=True).order_by('-created_at'),
    }