import requests
import json
import re
import time
from datetime import datetime, timedelta
from django.conf import settings
from urllib.parse import quote
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class XUIClient:
    def __init__(self):
        self.base = settings.XUI_API_URL.rstrip('/')
        self.login_page = settings.XUI_LOGIN_PAGE
        self.login_action = settings.XUI_LOGIN_ACTION
        self.api_prefix = settings.XUI_API_PREFIX.rstrip('/')
        self.session = requests.Session()
        self.session.verify = False
        self.csrf_token = None
        self._login()

    def _login(self):
        # 1. GET страницы входа
        resp = self.session.get(f'{self.base}{self.login_page}')
        if resp.status_code != 200:
            raise Exception(f'Не удалось загрузить страницу входа (статус {resp.status_code})')

        match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', resp.text)
        if not match:
            match = re.search(r'<input\s+type="hidden"\s+name="_csrf"\s+value="([^"]+)"', resp.text)
        self.csrf_token = match.group(1) if match else None

        # 2. POST-запрос на вход
        data = {'username': settings.XUI_USERNAME, 'password': settings.XUI_PASSWORD}
        headers = {}
        if self.csrf_token:
            data['_csrf'] = self.csrf_token
            headers['X-CSRF-TOKEN'] = self.csrf_token
            headers['X-XSRF-TOKEN'] = self.csrf_token
        headers['Referer'] = f'{self.base}{self.login_page}'

        resp = self.session.post(
            f'{self.base}{self.login_action}',
            data=data,
            headers=headers
        )
        if resp.status_code != 200:
            raise Exception(f'Ошибка входа (статус {resp.status_code}): {resp.text[:200]}')

        try:
            json_resp = resp.json()
            if isinstance(json_resp, str):
                json_resp = json.loads(json_resp)
            if not json_resp.get('success'):
                raise Exception(f'Ошибка входа: {json_resp.get("msg")}')
        except ValueError:
            if 'dashboard' not in resp.text.lower() and 'inbounds' not in resp.text.lower():
                raise Exception('Не удалось войти в панель (неизвестный ответ)')

    def _add_csrf_header(self, headers=None):
        if headers is None:
            headers = {}
        if self.csrf_token:
            headers['X-CSRF-TOKEN'] = self.csrf_token
        return headers

    def _make_dict(self, response):
        try:
            data = response.json()
            if isinstance(data, str):
                data = json.loads(data)
            if not isinstance(data, dict):
                raise ValueError(f'Получен {type(data)}')
            return data
        except Exception:
            raise Exception(f'Сервер вернул не JSON: {response.text[:200]}')

    def add_client(self, email, uuid, inbound_id):
        expiry_time = int((datetime.now() + timedelta(days=30)).timestamp() * 1000)
        url = f'{self.base}{self.api_prefix}/clients/add'

        client_data = {
            'email': email,
            'id': uuid,
            'enable': True,
            'expiryTime': expiry_time,
            'totalGB': 0,
            'limitIp': 0,
        }
        if inbound_id == settings.XUI_INBOUND_ID_VLESS:
            client_data.update({'flow': 'xtls-rprx-vision', 'security': 'reality'})
        else:
            client_data.update({'password': uuid, 'security': 'auto'})

        payload = {'inboundIds': [inbound_id], 'client': client_data}
        resp = self.session.post(url, json=payload, headers=self._add_csrf_header({'Content-Type': 'application/json'}))
        data = self._make_dict(resp)
        if not data.get('success'):
            raise Exception(f'Ошибка создания клиента: {data.get("msg")}')

        # Получаем реальный UUID и числовой client_id
        real_uuid = None
        client_id = None

        # Пытаемся извлечь сразу из ответа (редко)
        obj = data.get('obj')
        if isinstance(obj, dict):
            real_uuid = obj.get('id')
            client_id = obj.get('id')  # иногда числовой id лежит здесь

        # Если не получилось – запрашиваем через отдельный эндпоинт
        if not real_uuid:
            for attempt in range(5):
                time.sleep(2)
                real_uuid = self._fetch_client_uuid(email)
                if real_uuid:
                    break

        if real_uuid:
            client_id = self._fetch_client_id(email)

        # subId (для ссылок подписки)
        sub_id = obj.get('subId') if isinstance(obj, dict) else None
        if not sub_id:
            sub_id = self._fetch_sub_id(email)

        return {
            'uuid': real_uuid or uuid,
            'sub_id': sub_id,
            'client_id': client_id
        }

    def _fetch_client_uuid(self, email):
        """Возвращает UUID клиента (поле 'uuid' из ответа /clients/get/{email})."""
        encoded_email = quote(email, safe='')
        url = f'{self.base}{self.api_prefix}/clients/get/{encoded_email}'
        for attempt in range(6):
            resp = self.session.get(url, headers=self._add_csrf_header())
            try:
                data = self._make_dict(resp)
            except Exception:
                time.sleep(2)
                continue
            if data.get('success'):
                obj = data.get('obj')
                if isinstance(obj, dict):
                    client_obj = obj.get('client')
                    if isinstance(client_obj, dict) and client_obj.get('uuid'):
                        return client_obj['uuid']
            time.sleep(2)
        return None

    def _fetch_client_id(self, email):
        """Возвращает числовой ID клиента (поле 'id' из ответа /clients/get/{email})."""
        encoded_email = quote(email, safe='')
        url = f'{self.base}{self.api_prefix}/clients/get/{encoded_email}'
        resp = self.session.get(url, headers=self._add_csrf_header())
        try:
            data = self._make_dict(resp)
        except Exception:
            return None
        if data.get('success'):
            obj = data.get('obj')
            if isinstance(obj, dict):
                client_obj = obj.get('client')
                if isinstance(client_obj, dict):
                    return client_obj.get('id')   # числовой ID
        return None

    def _fetch_sub_id(self, email):
        url = f'{self.base}{self.api_prefix}/clients/list/paged?page=1&pageSize=50&sort=createdAt&order=ascend'
        resp = self.session.get(url, headers=self._add_csrf_header())
        try:
            data = self._make_dict(resp)
        except Exception:
            return None
        if data.get('success'):
            obj = data.get('obj')
            items = []
            if isinstance(obj, list):
                items = obj
            elif isinstance(obj, dict) and 'items' in obj:
                items = obj['items']
            for client in items:
                if isinstance(client, dict) and client.get('email') == email:
                    return client.get('subId')
        return None

    def get_client_info(self, email):
        url = f'{self.base}{self.api_prefix}/clients/list/paged?page=1&pageSize=50&sort=createdAt&order=ascend'
        resp = self.session.get(url, headers=self._add_csrf_header())
        try:
            data = self._make_dict(resp)
        except Exception:
            return None
        if not data.get('success'):
            return None
        obj = data.get('obj')
        items = []
        if isinstance(obj, list):
            items = obj
        elif isinstance(obj, dict) and 'items' in obj:
            items = obj['items']
        for client in items:
            if isinstance(client, dict) and client.get('email') == email:
                return {
                    'enable': client.get('enable', False),
                    'expiryTime': client.get('expiryTime', 0),
                    'subId': client.get('subId'),
                    'uuid': client.get('id'),
                }
        return None

    def get_client_traffic(self, email):
        url = f'{self.base}{self.api_prefix}/clients/list/paged?page=1&pageSize=50&sort=createdAt&order=ascend'
        resp = self.session.get(url, headers=self._add_csrf_header())
        try:
            data = self._make_dict(resp)
        except Exception:
            return None
        if not data.get('success'):
            return None
        obj = data.get('obj')
        items = []
        if isinstance(obj, list):
            items = obj
        elif isinstance(obj, dict) and 'items' in obj:
            items = obj['items']
        for client in items:
            if isinstance(client, dict) and client.get('email') == email:
                up = client.get('up')
                down = client.get('down')
                total = client.get('totalGB', 0)
                if up is None and 'traffic' in client and isinstance(client['traffic'], dict):
                    up = client['traffic'].get('up')
                    down = client['traffic'].get('down')
                return {
                    'upload': up if up is not None else 0,
                    'download': down if down is not None else 0,
                    'total': total if total is not None else 0,
                }
        return None

    def update_client(self, email, sub_id, uuid, expiry_time=None, enable=None, total_gb=None):
        """Обновляет клиента. email – для URL, в теле id (uuid) и subId."""
        from urllib.parse import quote
        encoded_email = quote(email, safe='')
        url = f'{self.base}{self.api_prefix}/clients/update/{encoded_email}'

        client_data = {
            'id': uuid,  # UUID клиента (как в браузере)
            'subId': sub_id,  # короткий subId
            'email': email,
            'enable': enable if enable is not None else True,
            'expiryTime': int(expiry_time.timestamp() * 1000) if expiry_time else 0,
            'totalGB': total_gb if total_gb is not None else 0,
            'limitIp': 0,
            'flow': '',
            'security': 'auto',
            'password': '',
            'auth': '',
            'comment': '',
            'tgId': 0,
            'reset': 0,
            'group': '',
        }

        payload = client_data  # браузер отправляет плоский объект, а не {client: ...}
        resp = self.session.post(url, json=payload, headers=self._add_csrf_header({'Content-Type': 'application/json'}))
        data = self._make_dict(resp)
        if not data.get('success'):
            raise Exception(f'Ошибка обновления клиента: {data.get("msg")}')

    def delete_client(self, email):
        """Удаляет клиента по email (в URL кодируется)."""
        from urllib.parse import quote
        encoded_email = quote(email, safe='')
        url = f'{self.base}{self.api_prefix}/clients/del/{encoded_email}'
        resp = self.session.post(url, headers=self._add_csrf_header())
        data = self._make_dict(resp)
        if not data.get('success'):
            raise Exception(f'Ошибка удаления клиента: {data.get("msg")}')