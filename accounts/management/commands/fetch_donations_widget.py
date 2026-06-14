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
        widget_url = (
            'https://www.donationalerts.com/widget/lastdonations'
            '?alert_type=1,4,6,8,7,10,9,3,2,5,11,12,13,14,15,16,17,19,20,27,28,29,30,31,32,33,34,35,36'
            '&limit=100'
        )

        try:
            resp = requests.get(widget_url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка загрузки виджета: {e}'))
            return

        html_content = resp.text

        # Ищем все блоки с донатами (обычно <div class="donation"> или <li>)
        # Используем регулярное выражение, чтобы найти блоки с суммой и сообщением
        donation_blocks = re.findall(
            r'<div[^>]*class="[^"]*donation[^"]*"[^>]*>(.*?)</div>',
            html_content,
            re.DOTALL | re.IGNORECASE
        )

        if not donation_blocks:
            # Если не нашли по классу, попробуем найти все li с data-donation-id
            donation_blocks = re.findall(
                r'<li[^>]*data-donation-id="([^"]*)"[^>]*>(.*?)</li>',
                html_content,
                re.DOTALL | re.IGNORECASE
            )

        processed = 0
        for block in donation_blocks:
            # Если блок пришёл как кортеж (data-id + содержимое) – обрабатываем
            if isinstance(block, tuple):
                donation_id = block[0]
                block_content = block[1]
            else:
                # Ищем data-donation-id внутри div
                id_match = re.search(r'data-donation-id="([^"]*)"', block)
                donation_id = id_match.group(1) if id_match else None
                block_content = block

            if not donation_id:
                continue

            if Donation.objects.filter(donation_id=donation_id).exists():
                continue

            # Извлекаем сумму
            amount_match = re.search(r'([\d\s]+(?:\.\d{1,2})?)\s*(RUB|USD|EUR|₽|\$|€)', block_content, re.IGNORECASE)
            if amount_match:
                amount_str = amount_match.group(1).replace(' ', '')
                amount = float(amount_str)
                currency = amount_match.group(2)
                if currency in ('₽', 'RUB'):
                    currency = 'RUB'
                elif currency in ('$', 'USD'):
                    currency = 'USD'
                elif currency in ('€', 'EUR'):
                    currency = 'EUR'
            else:
                continue

            # Извлекаем сообщение (обычно внутри <div class="message">)
            msg_match = re.search(r'<div[^>]*class="[^"]*message[^"]*"[^>]*>(.*?)</div>', block_content, re.DOTALL)
            message = ''
            if msg_match:
                message = html.unescape(re.sub(r'<[^>]+>', '', msg_match.group(1))).strip()

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

            # Проверка минимальной суммы
            min_amount = settings.MIN_DONATION_AMOUNT_RUB
            if currency == 'RUB' and amount < min_amount:
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

            # Активация/продление
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
                self.stdout.write(self.style.SUCCESS(f'Активирована подписка для {user.username} (донат #{donation_id})'))
            else:
                self.stdout.write(self.style.WARNING(f'Донат #{donation_id} не обработан (код не найден)'))

            processed += 1

        if processed == 0:
            self.stdout.write('Нет новых донатов.')
        else:
            self.stdout.write(f'Обработано донатов: {processed}')