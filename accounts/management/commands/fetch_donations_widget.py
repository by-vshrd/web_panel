import requests
import re
import html
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from accounts.models import Profile, Donation

class Command(BaseCommand):
    help = 'Парсит виджет последних донатов Donation Alerts и активирует подписки по кодам'

    def handle(self, *args, **options):
        # Укажите ваш никнейм на Donation Alerts (тот, что в ссылке https://www.donationalerts.com/r/...)
        streamer = 'Vashardi'   # <-- замените на ваш реальный никнейм
        widget_url = (
            f'https://www.donationalerts.com/widget/lastdonations'
            f'?streamer={streamer}'
            f'&alert_type=1,4,6,8,7,10,9,3,2,5,11,12,13,14,15,16,17,19,20,27,28,29,30,31,32,33,34,35,36'
            f'&limit=100'
        )

        try:
            resp = requests.get(widget_url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка загрузки виджета: {e}'))
            return

        html_content = resp.text

        # Ищем все вхождения сообщений и сумм (универсальный подход)
        # Паттерн: "отправил 200 RUB" или "$5.00"
        # Ищем строки вида "никнейм отправил X валюту" и рядом сообщение
        donation_pattern = re.compile(
            r'(?:<[^>]*>)?\s*(?P<username>[\w]+)\s*отправил\s*(?P<amount>[\d\s]+(?:\.\d{1,2})?)\s*(?P<currency>[A-Z]{3}|[₽$€])\s*(?:<[^>]*>)?\s*(?:<[^>]*>)?(?P<message>.*?)(?:<[^>]*>)?$',
            re.MULTILINE | re.DOTALL
        )

        processed = 0
        for match in donation_pattern.finditer(html_content):
            amount_str = match.group('amount').replace(' ', '')
            amount = float(amount_str)
            currency_raw = match.group('currency')
            if currency_raw in ('₽', 'RUB'):
                currency = 'RUB'
            elif currency_raw in ('$', 'USD'):
                currency = 'USD'
            elif currency_raw in ('€', 'EUR'):
                currency = 'EUR'
            else:
                currency = currency_raw

            raw_message = match.group('message').strip()
            # Очищаем от HTML-тегов
            message = html.unescape(re.sub(r'<[^>]+>', '', raw_message)).strip()

            # Генерируем уникальный ID из хэша сообщения+суммы (так как ID в виджете может не быть)
            import hashlib
            donation_id = hashlib.md5(f'{amount}{currency}{message}'.encode()).hexdigest()

            if Donation.objects.filter(donation_id=donation_id).exists():
                continue

            # Поиск кода активации
            user = None
            code_match = re.search(r'VSH-\w{4}-[\w]+', message)
            if code_match:
                code = code_match.group(0)
                try:
                    profile = Profile.objects.get(activation_code=code)
                    user = profile.user
                except Profile.DoesNotExist:
                    pass

            # Проверка минимальной суммы (можно временно убрать для теста)
            min_amount = settings.MIN_DONATION_AMOUNT_RUB
            if currency == 'RUB' and amount < min_amount:
                Donation.objects.create(
                    donation_id=donation_id,
                    amount=amount,
                    currency=currency,
                    message=message,
                    processed=False,
                    user=user
                )
                continue

            # Активация/продление
            if user:
                days = settings.DEFAULT_DAYS_PER_DONATION
                for profile in user.profiles.all():
                    if profile.is_subscription_active():
                        profile.subscription_expiry += timedelta(days=days)
                    else:
                        profile.subscription_expiry = timezone.now() + timedelta(days=days)
                    profile.save()
                processed_flag = True
            else:
                processed_flag = False

            Donation.objects.create(
                donation_id=donation_id,
                amount=amount,
                currency=currency,
                message=message,
                processed=processed_flag,
                user=user
            )

            if processed_flag:
                self.stdout.write(self.style.SUCCESS(f'Активирована подписка для {user.username} (донат {donation_id})'))
            else:
                self.stdout.write(self.style.WARNING(f'Донат {donation_id} не обработан (код не найден)'))

            processed += 1

        if processed == 0:
            self.stdout.write('Нет новых донатов.')
        else:
            self.stdout.write(f'Обработано донатов: {processed}')