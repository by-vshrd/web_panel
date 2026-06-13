from django.apps import AppConfig
from django.db import connection, ProgrammingError

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        alterations = [
            "ALTER TABLE accounts_profile ADD COLUMN IF NOT EXISTS protocol varchar(10) DEFAULT 'hysteria'",
            "ALTER TABLE accounts_profile ADD COLUMN IF NOT EXISTS created_at timestamp with time zone DEFAULT now()",
            "ALTER TABLE accounts_profile DROP CONSTRAINT IF EXISTS accounts_profile_user_id_key",
        ]
        try:
            with connection.cursor() as cursor:
                for sql in alterations:
                    try:
                        cursor.execute(sql)
                    except ProgrammingError:
                        pass
        except Exception:
            pass