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

def unlock_funds(wallet, amount):
    if amount <= 0:
        raise ValueError("Unlock amount must be greater than zero.")

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

        if wallet.locked < amount:
            raise InsufficientFunds("Not enough locked balance.")

        wallet.locked = wallet.locked - amount
        wallet.available = wallet.available + amount
        wallet.save()

        reference = uuid.uuid4()
        LedgerEntry.objects.create(
            wallet=wallet,
            bucket=LedgerEntry.Bucket.LOCKED,
            amount=-amount,
            kind=LedgerEntry.Kind.UNLOCK,
            reference=reference,
        )
        LedgerEntry.objects.create(
            wallet=wallet,
            bucket=LedgerEntry.Bucket.AVAILABLE,
            amount=amount,
            kind=LedgerEntry.Kind.UNLOCK,
            reference=reference,
        )

    return wallet


def _get_locked_wallet(pk):
    return Wallet.objects.select_for_update().get(pk=pk)


def release_funds(seller_wallet, buyer_wallet, amount):
    if amount <= 0:
        raise ValueError("Release amount must be greater than zero.")
    if seller_wallet.pk == buyer_wallet.pk:
        raise ValueError("Seller and buyer wallets must be different.")

    with transaction.atomic():
        if seller_wallet.pk < buyer_wallet.pk:
            seller = _get_locked_wallet(seller_wallet.pk)
            buyer = _get_locked_wallet(buyer_wallet.pk)
        else:
            buyer = _get_locked_wallet(buyer_wallet.pk)
            seller = _get_locked_wallet(seller_wallet.pk)

        if seller.currency != buyer.currency:
            raise ValueError("Wallets must use the same currency.")
        if seller.locked < amount:
            raise InsufficientFunds("Not enough locked balance.")

        seller.locked = seller.locked - amount
        buyer.available = buyer.available + amount
        seller.save()
        buyer.save()

        reference = uuid.uuid4()
        LedgerEntry.objects.create(
            wallet=seller,
            bucket=LedgerEntry.Bucket.LOCKED,
            amount=-amount,
            kind=LedgerEntry.Kind.RELEASE,
            reference=reference,
        )
        LedgerEntry.objects.create(
            wallet=buyer,
            bucket=LedgerEntry.Bucket.AVAILABLE,
            amount=amount,
            kind=LedgerEntry.Kind.RELEASE,
            reference=reference,
        )

    return seller, buyer

def ledger_total(wallet, bucket):
    result = wallet.entries.filter(bucket=bucket).aggregate(total=Sum("amount"))
    return result["total"] or Decimal("0")