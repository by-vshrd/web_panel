from django.apps import AppConfig
from django.db import connection

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # Исправляем отсутствующее поле protocol в уже существующей таблице
        try:
            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE accounts_profile ADD COLUMN IF NOT EXISTS protocol varchar(10) DEFAULT 'hysteria'")
        except Exception:
            pass