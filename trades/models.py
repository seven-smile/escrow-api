from django.conf import settings
from django.db import models
from django.db.models import F, Q

from wallets.models import Wallet

class Offer(models.Model):
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="offers",
    )
    currency = models.CharField(max_length=10, choices=Wallet.Currency.choices)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    min_amount = models.DecimalField(max_digits=20, decimal_places=8)
    max_amount = models.DecimalField(max_digits=20, decimal_places=8)
    terms = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gt=0),
                name="offer_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(min_amount__gt=0),
                name="offer_min_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(max_amount__gte=F("min_amount")),
                name="offer_max_not_below_min",
            ),
        ]

    def __str__(self):
        return f"Offer {self.pk}: {self.seller} sells {self.currency} at GHS {self.price}"
    
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
    offer = models.ForeignKey(
        Offer,
        on_delete=models.PROTECT,
        related_name="trades",
        null=True,
        blank=True,
    )
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
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
            models.UniqueConstraint(
                fields=["buyer", "seller"],
                condition=Q(status="awaiting_payment"),
                name="one_unpaid_trade_per_buyer_and_seller",
            ),
        ]

    def __str__(self):
        return f"Trade {self.pk}: {self.seller} sells {self.amount} {self.currency} to {self.buyer} ({self.status})"

class TradeEvent(models.Model):
    trade = models.ForeignKey(
        Trade,
        on_delete=models.PROTECT,
        related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="trade_events",
    )
    from_status = models.CharField(
        max_length=20, choices=Trade.Status.choices, blank=True
    )
    to_status = models.CharField(max_length=20, choices=Trade.Status.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Trade {self.trade_id}: {self.from_status or 'new'} -> {self.to_status} by {self.actor}"
    