import io, qrcode, json, requests
from uuid import uuid4
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from .forms import SignUpForm
from .models import Profile
from .api import XUIClient
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

@login_required
def dashboard(request):
    user = request.user
    profiles = Profile.objects.filter(user=user).order_by('protocol')

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

    Profile.objects.create(
        user=request.user,
        protocol=protocol,
        vpn_email=email,
        vpn_uuid=vpn_uuid,
        vpn_inbound_id=inbound_id,
        vpn_sub_id=sub_id,
        subscription_expiry=timezone.now() + timedelta(days=30),
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