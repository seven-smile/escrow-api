import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .models import LedgerEntry


def deposit(wallet, amount):
    if amount <= 0:
        raise ValueError("Deposit amount must be greater than zero.")

    with transaction.atomic():
        wallet.available = wallet.available + amount
        wallet.save()

        LedgerEntry.objects.create(
            wallet=wallet,
            bucket=LedgerEntry.Bucket.AVAILABLE,
            amount=amount,
            kind=LedgerEntry.Kind.DEPOSIT,
            reference=uuid.uuid4(),
        )


def ledger_total(wallet, bucket):
    result = wallet.entries.filter(bucket=bucket).aggregate(total=Sum("amount"))
    return result["total"] or Decimal("0")