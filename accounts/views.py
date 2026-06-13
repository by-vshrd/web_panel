import io, qrcode, json, requests
from uuid import uuid4
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from .forms import SignUpForm
from .models import Profile, AdminSettings
from .api import XUIClient
import urllib3
from django.contrib.auth.models import User
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
        sub_id = result['sub_id']
    except Exception as e:
        return HttpResponse(f'Ошибка создания: {e}', status=500)

    # Настройки по умолчанию
    admin_cfg = AdminSettings.load()
    Profile.objects.create(
        user=request.user,
        protocol=protocol,
        vpn_email=email,
        vpn_uuid=vpn_uuid,
        vpn_inbound_id=inbound_id,
        vpn_sub_id=sub_id,
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
        if profile_id:
            profile = get_object_or_404(Profile, pk=profile_id, user=user)
            new_expiry = request.POST.get('expiry')
            new_enable = request.POST.get('enable') == 'on'
            new_total_gb = request.POST.get('total_gb')

            if new_expiry:
                try:
                    profile.subscription_expiry = timezone.make_aware(
                        datetime.strptime(new_expiry, '%Y-%m-%d')
                    )
                except ValueError:
                    pass
            else:
                profile.subscription_expiry = None

            if not new_enable:
                profile.subscription_expiry = timezone.now() - timedelta(days=1)

            if new_total_gb is not None and new_total_gb.isdigit():
                profile.total_gb = int(new_total_gb)

            profile.save()
            return redirect('manage_user', user_id=user.id)

    return render(request, 'manage_user.html', {'user_obj': user, 'profiles': profiles})


@staff_member_required
def admin_settings(request):
    settings_obj = AdminSettings.load()
    if request.method == 'POST':
        settings_obj.default_days = int(request.POST.get('default_days', 30))
        settings_obj.default_traffic_gb = int(request.POST.get('default_traffic_gb', 0))
        settings_obj.save()
        return redirect('admin_settings')

    return render(request, 'admin_settings.html', {'settings': settings_obj})