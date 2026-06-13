from django.apps import AppConfig
from django.db import connection, ProgrammingError

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        """Добавляет недостающие колонки в уже существующую таблицу (исправление для Neon)."""
        alterations = [
            "ALTER TABLE accounts_profile ADD COLUMN IF NOT EXISTS protocol varchar(10) DEFAULT 'hysteria'",
            "ALTER TABLE accounts_profile ADD COLUMN IF NOT EXISTS created_at timestamp with time zone DEFAULT now()",
            # Если позже появятся ещё поля, добавьте их сюда аналогично
        ]
        try:
            with connection.cursor() as cursor:
                for sql in alterations:
                    try:
                        cursor.execute(sql)
                    except ProgrammingError:
                        pass  # колонка уже существует, ничего не делаем
        except Exception:
            pass  # на случай, если таблицы ещё нет (первый запуск)