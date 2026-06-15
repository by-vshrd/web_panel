import io
import qrcode
import json
import requests
import re
import secrets
from uuid import uuid4
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .forms import SignUpForm
from .models import Profile, AdminSettings, Donation
from .api import XUIClient
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ---------- Публичные страницы ----------
def home(request):
    return render(request, 'home.html')


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = 'signup.html'
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect('dashboard')


@require_GET
def server_status(request):
    try:
        requests.get(settings.XUI_API_URL, timeout=5, verify=False)
        online = True
    except Exception:
        online = False
    return JsonResponse({'online': online})


# ---------- Личный кабинет ----------
@login_required
def dashboard(request):
    user = request.user
    profiles = Profile.objects.filter(user=user).order_by('protocol')

    # Синхронизация с панелью
    for profile in profiles:
        if profile.vpn_email:
            try:
                client = XUIClient()
                info = client.get_client_info(profile.vpn_email)
                if info is not None:
                    expiry_ms = info.get('expiryTime')
                    if expiry_ms and expiry_ms != 0:
                        naive_expiry = datetime.fromtimestamp(expiry_ms / 1000)
                        aware_expiry = timezone.make_aware(naive_expiry)
                        profile.subscription_expiry = aware_expiry
                    else:
                        profile.subscription_expiry = None
                    if not info.get('enable', True):
                        profile.subscription_expiry = timezone.now() - timedelta(days=1)
                    profile.save()
            except Exception:
                pass

    # Трафик
    for profile in profiles:
        if profile.is_subscription_active():
            try:
                client = XUIClient()
                profile.traffic = client.get_client_traffic(profile.vpn_email)
            except Exception:
                profile.traffic = None
        else:
            profile.traffic = None

    existing_protocols = profiles.values_list('protocol', flat=True)
    available_protocols = [p for p in ['hysteria', 'vless'] if p not in existing_protocols]

    context = {
        'profiles': profiles,
        'available_protocols': available_protocols,
    }
    return render(request, 'dashboard.html', context)


@login_required
@require_POST
def create_profile(request):
    protocol = request.POST.get('protocol')
    if protocol not in ('hysteria', 'vless'):
        return HttpResponse('Неверный протокол', status=400)

    if Profile.objects.filter(user=request.user, protocol=protocol).exists():
        return HttpResponse('Профиль для этого протокола уже существует', status=400)

    inbound_id = settings.XUI_INBOUND_ID_HYSTERIA if protocol == 'hysteria' else settings.XUI_INBOUND_ID_VLESS
    email = f'{request.user.username}_{protocol}@vpn.local'
    vpn_uuid = uuid4()

    try:
        client = XUIClient()
        result = client.add_client(email, str(vpn_uuid), inbound_id)
        real_uuid = result['uuid']
        sub_id = result['sub_id']
        client_id = result.get('client_id')
    except Exception as e:
        return HttpResponse(f'Ошибка создания: {e}', status=500)

    admin_cfg = AdminSettings.load()
    Profile.objects.create(
        user=request.user,
        protocol=protocol,
        vpn_email=email,
        vpn_uuid=real_uuid,
        vpn_inbound_id=inbound_id,
        vpn_sub_id=sub_id,
        vpn_client_id=client_id,
        subscription_expiry=timezone.now() + timedelta(days=admin_cfg.default_days),
        total_gb=admin_cfg.default_traffic_gb,
    )
    return redirect('dashboard')


@login_required
def qr_code(request, protocol):
    try:
        profile = Profile.objects.get(user=request.user, protocol=protocol)
    except Profile.DoesNotExist:
        return HttpResponse('Профиль не найден', status=404)

    if not profile.is_subscription_active():
        return HttpResponse('Подписка истекла', status=403)

    sub_link = f'https://{settings.XUI_SERVER_DOMAIN}:2096/sub/{profile.vpn_sub_id}'
    qr = qrcode.make(sub_link)
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')


@login_required
def subscription_link(request, protocol):
    try:
        profile = Profile.objects.get(user=request.user, protocol=protocol)
    except Profile.DoesNotExist:
        return HttpResponse('Профиль не найден', status=404)

    if not profile.is_subscription_active():
        return HttpResponse('Подписка истекла', status=403)

    sub_link = f'https://{settings.XUI_SERVER_DOMAIN}:2096/sub/{profile.vpn_sub_id}'
    return HttpResponse(sub_link)


@login_required
def get_activation_code(request):
    user = request.user
    profile = user.profiles.first()
    if not profile:
        return HttpResponse('Сначала создайте хотя бы один VPN‑профиль', status=400)

    if not profile.activation_code:
        code = f"VSH-{user.username[:4].upper()}-{secrets.token_hex(4)}"
        while Profile.objects.filter(activation_code=code).exists():
            code = f"VSH-{user.username[:4].upper()}-{secrets.token_hex(4)}"
        profile.activation_code = code
        profile.save()
    return HttpResponse(profile.activation_code)


def logout_view(request):
    logout(request)
    return redirect('home')


# ---------- Административные функции ----------
@staff_member_required
def admin_dashboard(request):
    total_users = User.objects.count()
    total_profiles = Profile.objects.count()
    active_profiles = Profile.objects.filter(subscription_expiry__gt=timezone.now()).count()
    expire_soon = Profile.objects.filter(
        subscription_expiry__gt=timezone.now(),
        subscription_expiry__lt=timezone.now() + timedelta(days=7)
    ).count()

    users = User.objects.prefetch_related('profiles').all().order_by('-date_joined')

    context = {
        'total_users': total_users,
        'total_profiles': total_profiles,
        'active_profiles': active_profiles,
        'expire_soon': expire_soon,
        'users': users,
        'panel_url': settings.XUI_API_URL,
    }
    return render(request, 'admin_dashboard.html', context)


@staff_member_required
def manage_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    profiles = user.profiles.all()

    if request.method == 'POST':
        profile_id = request.POST.get('profile_id')
        action = request.POST.get('action')

        if action == 'sync_sub_id':
            profile = get_object_or_404(Profile, pk=profile_id, user=user)
            try:
                client = XUIClient()
                fresh_sub_id = client.get_sub_id_by_email(profile.vpn_email)
                if fresh_sub_id:
                    profile.vpn_sub_id = fresh_sub_id
                    profile.save()
                    messages.success(request, f'sub_id обновлён: {fresh_sub_id}')
                else:
                    messages.error(request, 'Не удалось найти клиента в панели по email.')
            except Exception as e:
                messages.error(request, f'Ошибка API: {e}')
            return redirect('manage_user', user_id=user.id)

        # Сохранение изменений профиля
        profile = get_object_or_404(Profile, pk=profile_id, user=user)
        new_email = request.POST.get('email', '').strip()
        new_expiry = request.POST.get('expiry', '')
        new_enable = request.POST.get('enable') == 'on'
        new_total_gb = request.POST.get('total_gb', '')

        expiry_dt = None
        if new_expiry:
            try:
                naive = datetime.strptime(new_expiry, '%Y-%m-%d')
                expiry_dt = timezone.make_aware(naive)
            except ValueError:
                messages.error(request, 'Неверный формат даты')
                return redirect('manage_user', user_id=user.id)

        if not profile.vpn_sub_id:
            messages.error(request, 'Нет sub_id для синхронизации. Сначала синхронизируйте ID.')
            return redirect('manage_user', user_id=user.id)

        try:
            client = XUIClient()
            client.update_client(
                email=profile.vpn_email if not new_email else new_email,
                sub_id=profile.vpn_sub_id,
                uuid=str(profile.vpn_uuid),
                expiry_time=expiry_dt,
                enable=new_enable,
                total_gb=int(new_total_gb) if new_total_gb.isdigit() else None
            )
        except Exception as e:
            messages.error(request, f'Ошибка API: {e}')
            return redirect('manage_user', user_id=user.id)

        if new_email:
            profile.vpn_email = new_email
        profile.subscription_expiry = expiry_dt
        if not new_enable:
            profile.subscription_expiry = timezone.now() - timedelta(days=1)
        if new_total_gb.isdigit():
            profile.total_gb = int(new_total_gb)
        profile.save()
        messages.success(request, 'Профиль обновлён.')
        return redirect('manage_user', user_id=user.id)

    context = {'user_obj': user, 'profiles': profiles}
    return render(request, 'manage_user.html', context)


@staff_member_required
def delete_profile(request, profile_id):
    profile = get_object_or_404(Profile, pk=profile_id)
    user = profile.user
    if request.method == 'POST':
        if profile.vpn_sub_id:
            try:
                client = XUIClient()
                client.delete_client(profile.vpn_email)
            except Exception as e:
                messages.error(request, f'Ошибка API при удалении: {e}')
                return redirect('manage_user', user_id=user.id)
        profile.delete()
        messages.success(request, 'Профиль удалён.')
        return redirect('manage_user', user_id=user.id)
    return render(request, 'confirm_delete.html', {'object': profile, 'type': 'профиль'})


@staff_member_required
def delete_user(request, user_id):
    user_obj = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        for profile in user_obj.profiles.all():
            if profile.vpn_sub_id:
                try:
                    client = XUIClient()
                    client.delete_client(profile.vpn_email)
                except Exception:
                    pass
        user_obj.delete()
        messages.success(request, 'Пользователь и его профили удалены.')
        return redirect('admin_dashboard')
    return render(request, 'confirm_delete.html', {'object': user_obj, 'type': 'пользователя'})

@staff_member_required
def manual_extend(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        days = int(request.POST.get('days', 30))
        amount = request.POST.get('amount', '0').strip()
        try:
            xui = XUIClient()
        except Exception as e:
            messages.error(request, f'Не удалось подключиться к панели: {e}')
            return redirect('manage_user', user_id=user.id)

        for profile in user.profiles.all():
            if profile.subscription_expiry is None or profile.subscription_expiry < timezone.now():
                new_expiry = timezone.now() + timedelta(days=days)
            else:
                new_expiry = profile.subscription_expiry + timedelta(days=days)
            profile.subscription_expiry = new_expiry
            profile.save()
            # Синхронизация с панелью
            try:
                xui.update_client(
                    email=profile.vpn_email,
                    sub_id=profile.vpn_sub_id,
                    uuid=str(profile.vpn_uuid),
                    expiry_time=new_expiry,
                    enable=True,
                    total_gb=profile.total_gb
                )
            except Exception as e:
                messages.error(request, f'Ошибка синхронизации {profile.get_protocol_display()}: {e}')
        if amount:
            Donation.objects.create(
                donation_id=f'manual-{timezone.now().timestamp()}',
                source='manual',
                amount=float(amount),
                currency='RUB',
                message='Ручное продление администратором',
                processed=True,
                user=user
            )
        messages.success(request, f'Подписки продлены на {days} дней.')
        return redirect('manage_user', user_id=user.id)
    return redirect('manage_user', user_id=user.id)

@staff_member_required
def admin_settings(request):
    settings_obj = AdminSettings.load()
    if request.method == 'POST':
        settings_obj.default_days = int(request.POST.get('default_days', 30))
        settings_obj.default_traffic_gb = int(request.POST.get('default_traffic_gb', 0))
        settings_obj.save()
        return redirect('admin_settings')

    return render(request, 'admin_settings.html', {'settings': settings_obj})


@staff_member_required
def sync_profile_sub_id(request, profile_id):
    profile = get_object_or_404(Profile, pk=profile_id)
    if request.method == 'POST':
        try:
            client = XUIClient()
            fresh_sub_id = client.get_sub_id_by_email(profile.vpn_email)
            if fresh_sub_id:
                profile.vpn_sub_id = fresh_sub_id
                profile.save()
                messages.success(request, f'sub_id обновлён: {fresh_sub_id}')
            else:
                messages.error(request, 'Не удалось найти клиента в панели по email.')
        except Exception as e:
            messages.error(request, f'Ошибка API: {e}')
    return redirect('manage_user', user_id=profile.user.id)


# ---------- API-опрос донатов (защищённый эндпоинт) ----------
import traceback

@csrf_exempt
def fetch_donations_api(request):
    token = request.GET.get('token', '')
    if token != settings.CRON_SECRET:
        return HttpResponse('Invalid token', status=403)

    try:
        from .management.commands.fetch_donations_donatepay import Command
        cmd = Command()
        cmd.handle()
    except Exception as e:
        return HttpResponse(f'Error: {traceback.format_exc()}', status=500, content_type='text/plain')

    return HttpResponse('OK')

def faq(request):
    return render(request, 'faq.html')

@login_required
def payment_page(request):
    user = request.user
    profile = user.profiles.first()
    if not profile:
        return HttpResponse('Сначала создайте VPN‑профиль', status=400)

    # Генерируем код активации, если его ещё нет
    if not profile.activation_code:
        import secrets
        code = f"VSH-{user.username[:4].upper()}-{secrets.token_hex(4)}"
        while Profile.objects.filter(activation_code=code).exists():
            code = f"VSH-{user.username[:4].upper()}-{secrets.token_hex(4)}"
        profile.activation_code = code
        profile.save()

    # Последние 20 транзакций пользователя
    transactions = Donation.objects.filter(user=user).order_by('-created_at')[:20]

    context = {
        'profile': profile,
        'transactions': transactions,
    }
    return render(request, 'payment.html', context)