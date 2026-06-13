from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
import uuid

class Profile(models.Model):
    PROTOCOL_CHOICES = [
        ('hysteria', 'Hysteria2'),
        ('vless', 'VLESS'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='profiles')
    protocol = models.CharField(max_length=10, choices=PROTOCOL_CHOICES)
    vpn_email = models.EmailField(unique=True)
    vpn_uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    vpn_inbound_id = models.IntegerField()
    vpn_sub_id = models.CharField(max_length=255, blank=True, null=True)
    subscription_expiry = models.DateTimeField(null=True, blank=True)
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