import requests
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Отладка – показывает HTML виджета Donation Alerts (игнорирует системные прокси)'

    def handle(self, *args, **options):
        streamer = 'pay_check_by_v'   # ← замените на ваш реальный никнейм
        widget_url = (
            f'https://www.donationalerts.com/widget/lastdonations'
            f'?streamer={streamer}'
            f'&alert_type=1,4,6,8,7,10,9,3,2,5,11,12,13,14,15,16,17,19,20,27,28,29,30,31,32,33,34,35,36'
            f'&limit=100'
        )

        try:
            # Игнорируем системные прокси, чтобы избежать ошибки SOCKS
            resp = requests.get(
                widget_url,
                timeout=15,
                proxies={"http": None, "https": None}   # ← отключаем прокси
            )
            resp.raise_for_status()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка загрузки: {e}'))
            return

        html = resp.text
        # Сохраняем HTML в файл
        with open('widget_debug.html', 'w', encoding='utf-8') as f:
            f.write(html)
        # Выводим первые 2000 символов в консоль
        self.stdout.write(html[:2000])
        self.stdout.write('…')
        self.stdout.write(self.style.SUCCESS('Полный HTML сохранён в widget_debug.html'))