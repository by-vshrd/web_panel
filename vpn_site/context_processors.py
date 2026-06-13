from django.conf import settings

def extra_settings(request):
    return {
        'XUI_API_URL': settings.XUI_API_URL,
    }