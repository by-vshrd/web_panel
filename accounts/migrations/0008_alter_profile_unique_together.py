from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_adminsettings_profile_total_gb'),  # замените на реальную предыдущую миграцию!
    ]
    operations = [
        # Здесь могут быть другие операции, если вы добавляли новые поля.
        # Но операцию AlterUniqueTogether нужно полностью удалить.
        # Если других операций нет, просто оставьте список пустым.
    ]