from django.apps import AppConfig
from django.db import connection, ProgrammingError
from django.db.utils import OperationalError

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # Проверяем, что таблицы уже существуют (первый запуск миграций)
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connections
        executor = MigrationExecutor(connections['default'])
        if not executor.loader.applied_migrations:
            return  # миграции ещё не применялись – не трогаем базу

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