import requests
import re
import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from accounts.models import Profile, Donation

class Command(BaseCommand):
    help = 'Опрашивает DonatePay API и активирует подписки по кодам (с детальной отладкой)'

    def handle(self, *args, **options):
        token = settings.DONATEPAY_API_TOKEN
        if not token:
            self.stdout.write(self.style.ERROR('Не задан DONATEPAY_API_TOKEN'))
            return

        last_donation = Donation.objects.filter(source='donatepay').order_by('-created_at').first()
        after_id = last_donation.donation_id if last_donation else None

        url = 'https://donatepay.ru/api/v1/transactions'
        params = {
            'access_token': token,
            'limit': 50,
            'order': 'ASC',
            'type': 'donation',
        }
        if after_id:
            params['after'] = after_id

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = requests.get(
                    url,
                    params=params,
                    timeout=15,
                    proxies={"http": None, "https": None}
                )
                if resp.status_code == 429:
                    self.stdout.write(self.style.WARNING(
                        f'429 – ожидание 60 секунд (попытка {attempt+1}/{max_retries})…'
                    ))
                    time.sleep(60)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Ошибка запроса: {e}'))
                return
        else:
            self.stdout.write(self.style.ERROR('Не удалось выполнить запрос.'))
            return

        if data.get('status') != 'success':
            self.stdout.write(self.style.ERROR(f"API error: {data.get('message', '')}"))
            return

        transactions = data.get('data', [])
        if not transactions:
            self.stdout.write('Нет новых транзакций.')
            return

        for tx in transactions:
            tx_id = str(tx.get('id'))
            if Donation.objects.filter(donation_id=tx_id).exists():
                continue

            status = tx.get('status', '')
            if status not in ('success', 'user'):
                continue

            amount = float(tx.get('sum', 0))
            currency = tx.get('currency', 'RUB')
            comment = tx.get('comment', '').strip()

            code_match = re.search(r'VSH-[\w-]+', comment)
            user = None
            if code_match:
                code = code_match.group(0)
                self.stdout.write(f'Найден код: {code}')
                try:
                    profile = Profile.objects.get(activation_code=code)
                    user = profile.user
                    self.stdout.write(self.style.SUCCESS(f'Пользователь: {user.username}'))
                except Profile.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'Код {code} не найден в базе'))
            else:
                self.stdout.write(f'Код не найден в комментарии: "{comment}"')

            min_amount = settings.MIN_DONATION_AMOUNT_RUB
            if currency == 'RUB' and amount < min_amount:
                Donation.objects.create(
                    donation_id=tx_id,
                    source='donatepay',
                    amount=amount,
                    currency=currency,
                    message=comment,
                    processed=False,
                    user=user
                )
                continue

            if user:
                days = settings.DEFAULT_DAYS_PER_DONATION
                self.stdout.write(f'Продлеваю на {days} дней…')
                for profile in user.profiles.all():
                    old = profile.subscription_expiry
                    if profile.is_subscription_active():
                        profile.subscription_expiry = old + timedelta(days=days)
                    else:
                        profile.subscription_expiry = timezone.now() + timedelta(days=days)
                    profile.save()
                    self.stdout.write(f'  {profile.protocol}: {old} -> {profile.subscription_expiry}')
                processed = True
            else:
                processed = False

            Donation.objects.create(
                donation_id=tx_id,
                source='donatepay',
                amount=amount,
                currency=currency,
                message=comment,
                processed=processed,
                user=user
            )

            if processed:
                self.stdout.write(self.style.SUCCESS(f'Активирована подписка для {user.username} (ID {tx_id})'))
            else:
                self.stdout.write(self.style.WARNING(f'Транзакция #{tx_id} не обработана'))