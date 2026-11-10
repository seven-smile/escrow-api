import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .models import LedgerEntry, Wallet

class InsufficientFunds(Exception):
    pass

def deposit(wallet, amount):
    if amount <= 0:
        raise ValueError("Deposit amount must be greater than zero.")

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        wallet.available = wallet.available + amount
        wallet.save()

        LedgerEntry.objects.create(
            wallet=wallet,
            bucket=LedgerEntry.Bucket.AVAILABLE,
            amount=amount,
            kind=LedgerEntry.Kind.DEPOSIT,
            reference=uuid.uuid4(),
        )

    return wallet


def lock_funds(wallet, amount):
    if amount <= 0:
        raise ValueError("Lock amount must be greater than zero.")

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

        if wallet.available < amount:
            raise InsufficientFunds("Not enough available balance.")

        wallet.available = wallet.available - amount
        wallet.locked = wallet.locked + amount
        wallet.save()

        reference = uuid.uuid4()
        LedgerEntry.objects.create(
            wallet=wallet,
            bucket=LedgerEntry.Bucket.AVAILABLE,
            amount=-amount,
            kind=LedgerEntry.Kind.LOCK,
            reference=reference,
        )
        LedgerEntry.objects.create(
            wallet=wallet,
            bucket=LedgerEntry.Bucket.LOCKED,
            amount=amount,
            kind=LedgerEntry.Kind.LOCK,
            reference=reference,
        )

    return wallet


def ledger_total(wallet, bucket):
    result = wallet.entries.filter(bucket=bucket).aggregate(total=Sum("amount"))
    return result["total"] or Decimal("0")