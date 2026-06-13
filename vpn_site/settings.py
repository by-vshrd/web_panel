import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'change-me-in-production')
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'vpn_site.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'vpn_site.wsgi.application'

try:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
            conn_max_age=600,
            ssl_require=True
        )
    }
except ImportError:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 3X-UI
XUI_API_URL = 'https://78.17.4.72:32894'
XUI_LOGIN_PAGE = '/login/panel/'   # здесь реально находится страница входа
XUI_LOGIN_ACTION = '/login/login'  # сюда отправляется POST (как в браузере)
XUI_API_PREFIX = '/login/panel/api'
# префикс API
XUI_SERVER_DOMAIN = os.environ.get('XUI_SERVER_DOMAIN', '78.17.4.72')             # для подписок (если нужен)
#XUI_API_URL = os.environ.get('XUI_API_URL', 'http://78.17.4.72:32894')
XUI_USERNAME = os.environ.get('XUI_USERNAME', 'UQdzfdpNIY')
XUI_PASSWORD = os.environ.get('XUI_PASSWORD', 'O7KcS5jTip')
XUI_INBOUND_ID_HYSTERIA = int(os.environ.get('XUI_INBOUND_ID_HYSTERIA', 5))
XUI_INBOUND_ID_VLESS = int(os.environ.get('XUI_INBOUND_ID_VLESS', 1))
#XUI_SERVER_DOMAIN = os.environ.get('XUI_SERVER_DOMAIN', 'http://78.17.4.72:32894')
#XUI_LOGIN_PAGE = '/login/'
#XUI_LOGIN_ACTION = '/login/login'
#XUI_API_PREFIX = '/login/panel/api'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/accounts/dashboard/'
LOGOUT_REDIRECT_URL = '/'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = ['https://*.onrender.com']
USE_X_FORWARDED_HOST = True