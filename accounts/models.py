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
    default_days = models.IntegerField(default=30)
    default_traffic_gb = models.IntegerField(default=0)
    footer_text = models.CharField(
        max_length=200,
        default='BETA-build v0.2 by V.',
        verbose_name='Текст в футере'
    )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

class Donation(models.Model):
    donation_id = models.CharField(max_length=100, unique=True)
    source = models.CharField(max_length=20, default='donationalerts')   # ← добавьте
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10)
    message = models.TextField(blank=True)
    processed = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    LEVEL_CHOICES = [
        ('info', 'Информация'),
        ('success', 'Успех'),
        ('warning', 'Предупреждение'),
        ('error', 'Ошибка'),
    ]

    text = models.TextField(verbose_name='Текст уведомления')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info', verbose_name='Тип')
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'

    def __str__(self):
        return f'{self.get_level_display()}: {self.text[:50]}'