from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

class Wallet(models.Model):
    class Currency(models.TextChoices):
        USDT = "USDT", "Tether (USDT)"
        BTC = "BTC", "Bitcoin (BTC)"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wallets",
    )
    currency = models.CharField(max_length=10, choices=Currency.choices)
    available = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal("0")
    )
    locked = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal("0")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "currency"],
                name="one_wallet_per_user_per_currency",
            ),
            models.CheckConstraint(
                condition=Q(available__gte=0),
                name="wallet_available_not_negative",
            ),
            models.CheckConstraint(
                condition=Q(locked__gte=0),
                name="wallet_locked_not_negative",
            ),
        ]

    def __str__(self):
        return f"{self.user} {self.currency}: {self.available} available, {self.locked} locked"