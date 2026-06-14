import requests
import re
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from accounts.models import Profile, Donation

class Command(BaseCommand):
    help = 'Опрашивает Donation Alerts API и активирует подписки по кодам'

    def handle(self, *args, **options):
        token = settings.DONATION_ALERTS_API_TOKEN
        if not token:
            self.stdout.write(self.style.ERROR('Не задан DONATION_ALERTS_API_TOKEN'))
            return

        headers = {'Authorization': f'Bearer {token}'}
        url = settings.DONATION_ALERTS_API_URL

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка запроса к API: {e}'))
            return

        donations = data.get('data', [])
        if not donations:
            self.stdout.write('Нет новых донатов.')
            return

        # Обрабатываем в порядке возрастания ID (старые сначала)
        donations.sort(key=lambda d: d.get('id', 0))

        for donation in donations:
            donation_id = str(donation.get('id'))
            if Donation.objects.filter(donation_id=donation_id).exists():
                continue

            amount = float(donation.get('amount', 0))
            currency = donation.get('currency', 'RUB')
            message = donation.get('message', '').strip()

            # Ищем код активации в сообщении
            code_match = re.search(r'VSH-\w{4}-[\w]+', message)
            user = None
            if code_match:
                code = code_match.group(0)
                try:
                    profile = Profile.objects.get(activation_code=code)
                    user = profile.user
                except Profile.DoesNotExist:
                    pass

            # Проверяем минимальную сумму (если RUB)
            if currency == 'RUB' and amount < settings.MIN_DONATION_AMOUNT_RUB:
                # Недостаточная сумма – сохраняем без обработки
                Donation.objects.create(
                    donation_id=donation_id,
                    amount=amount,
                    currency=currency,
                    message=message,
                    processed=False,
                    user=user
                )
                continue

            # Активируем/продлеваем подписку
            if user:
                days = settings.DEFAULT_DAYS_PER_DONATION
                for profile in user.profiles.all():
                    if profile.is_subscription_active():
                        profile.subscription_expiry += timedelta(days=days)
                    else:
                        profile.subscription_expiry = timezone.now() + timedelta(days=days)
                    profile.save()
                processed = True
            else:
                processed = False

            Donation.objects.create(
                donation_id=donation_id,
                amount=amount,
                currency=currency,
                message=message,
                processed=processed,
                user=user
            )

            if processed:
                self.stdout.write(self.style.SUCCESS(
                    f'Активирована подписка для {user.username} (донат #{donation_id})'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f'Донат #{donation_id} не обработан (код не найден или пользователь отсутствует)'
                ))