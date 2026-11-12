from django.conf import settings
from django.db import models
from django.db.models import F, Q

from wallets.models import Wallet


class Trade(models.Model):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
        PAID = "paid", "Buyer marked as paid"
        RELEASED = "released", "Released to buyer"
        CANCELLED = "cancelled", "Cancelled"
        DISPUTED = "disputed", "Disputed"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchases",
    )
    currency = models.CharField(max_length=10, choices=Wallet.Currency.choices)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AWAITING_PAYMENT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="trade_amount_positive",
            ),
            models.CheckConstraint(
                condition=~Q(seller=F("buyer")),
                name="trade_seller_not_buyer",
            ),
        ]

    def __str__(self):
        return f"Trade {self.pk}: {self.seller} sells {self.amount} {self.currency} to {self.buyer} ({self.status})"