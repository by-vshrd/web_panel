from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
import uuid

class Profile(models.Model):
    PROTOCOL_CHOICES = [
        ('hysteria', 'Hysteria2'),
        ('vless', 'VLESS'),
    ]
    activation_code = models.CharField(max_length=20, blank=True, null=True, unique=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='profiles')
    protocol = models.CharField(max_length=10, choices=PROTOCOL_CHOICES)
    vpn_email = models.EmailField(unique=True)
    vpn_uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    vpn_inbound_id = models.IntegerField()
    vpn_sub_id = models.CharField(max_length=255, blank=True, null=True)
    vpn_client_id = models.IntegerField(null=True, blank=True)
    subscription_expiry = models.DateTimeField(null=True, blank=True)
    total_gb = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'protocol')

    def is_subscription_active(self):
        if self.subscription_expiry is None:
            return True
        return self.subscription_expiry > now()

    def days_left(self):
        if self.subscription_expiry is None:
            return -1
        delta = self.subscription_expiry - now()
        return max(0, delta.days)




class AdminSettings(models.Model):
    """Синглтон‑настройки по умолчанию (одна запись)."""
    default_days = models.IntegerField(default=30)
    default_traffic_gb = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Donation(models.Model):
    donation_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10)
    message = models.TextField(blank=True)
    processed = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)