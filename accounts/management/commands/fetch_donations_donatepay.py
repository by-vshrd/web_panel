import requests
import re
import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from accounts.models import Profile, Donation

class Command(BaseCommand):
    help = 'Опрашивает DonatePay API и активирует подписки по кодам'

    def handle(self, *args, **options):
        token = settings.DONATEPAY_API_TOKEN
        if not token:
            self.stdout.write(self.style.ERROR('Не задан DONATEPAY_API_TOKEN'))
            return

        last_donation = Donation.objects.filter(source='donatepay').order_by('-created_at').first()
        after_id = last_donation.donation_id if last_donation else None

        url = 'https://donatepay.ru/api/v1/transactions'
        headers = {'Authorization': f'Bearer {token}'}
        params = {'limit': 50}
        if after_id:
            params['after'] = after_id

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=15)
                if resp.status_code == 429:
                    self.stdout.write(self.style.WARNING(
                        f'Слишком много запросов (429). Ожидание 60 секунд перед повтором (попытка {attempt+1}/{max_retries})...'
                    ))
                    time.sleep(60)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Ошибка запроса к API: {e}'))
                return
        else:
            self.stdout.write(self.style.ERROR('Не удалось выполнить запрос после нескольких попыток.'))
            return

        transactions = data.get('data', [])
        if not transactions:
            self.stdout.write('Нет новых транзакций.')
            return

        for tx in transactions:
            tx_id = str(tx.get('id'))
            if Donation.objects.filter(donation_id=tx_id).exists():
                continue

            amount = float(tx.get('amount', 0))
            currency = tx.get('currency', 'RUB')
            message = tx.get('comment', '').strip()

            user = None
            code_match = re.search(r'VSH-\w{4}-[\w]+', message)
            if code_match:
                code = code_match.group(0)
                try:
                    profile = Profile.objects.get(activation_code=code)
                    user = profile.user
                except Profile.DoesNotExist:
                    pass

            min_amount = settings.MIN_DONATION_AMOUNT_RUB
            if currency == 'RUB' and amount < min_amount:
                Donation.objects.create(
                    donation_id=tx_id,
                    source='donatepay',
                    amount=amount,
                    currency=currency,
                    message=message,
                    processed=False,
                    user=user
                )
                continue

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
                donation_id=tx_id,
                source='donatepay',
                amount=amount,
                currency=currency,
                message=message,
                processed=processed,
                user=user
            )

            if processed:
                self.stdout.write(self.style.SUCCESS(f'Активирована подписка для {user.username} (транзакция #{tx_id})'))
            else:
                self.stdout.write(self.style.WARNING(f'Транзакция #{tx_id} не обработана (код не найден)'))