from django.db import transaction

from wallets.models import Wallet
from wallets.services import lock_funds, release_funds, unlock_funds

from .models import Offer, Trade, TradeEvent


class TradeError(Exception):
    pass

class InvalidMove(TradeError):
    pass

class NotAllowed(TradeError):
    pass

TRANSITIONS = {
    (Trade.Status.AWAITING_PAYMENT, Trade.Status.PAID): ["buyer"],
    (Trade.Status.AWAITING_PAYMENT, Trade.Status.CANCELLED): ["buyer"],
    (Trade.Status.PAID, Trade.Status.RELEASED): ["seller"],
    (Trade.Status.PAID, Trade.Status.DISPUTED): ["buyer", "seller"],
    (Trade.Status.DISPUTED, Trade.Status.RELEASED): ["support"],
    (Trade.Status.DISPUTED, Trade.Status.CANCELLED): ["support"],
}


def _role(trade, user):
    if user == trade.buyer:
        return "buyer"
    if user == trade.seller:
        return "seller"
    if user.is_staff:
        return "support"
    return None


def _check_allowed(trade, new_status, user):
    allowed_roles = TRANSITIONS.get((trade.status, new_status))
    if allowed_roles is None:
        raise InvalidMove(f"A trade can't go from {trade.status} to {new_status}.")
    if _role(trade, user) not in allowed_roles:
        raise NotAllowed(f"You aren't allowed to move this trade to {new_status}.")


def _get_locked_trade(pk):
    return Trade.objects.select_for_update().get(pk=pk)

def _record(trade, actor, from_status, note=""):
    TradeEvent.objects.create(
        trade=trade,
        actor=actor,
        from_status=from_status,
        to_status=trade.status,
        note=note,
    )

def open_trade(seller, buyer, currency, amount, offer=None, price=None):
    with transaction.atomic():
        seller_wallet = Wallet.objects.get(user=seller, currency=currency)
        Wallet.objects.get_or_create(user=buyer, currency=currency)
        lock_funds(seller_wallet, amount)
        trade = Trade.objects.create(
            seller=seller,
            buyer=buyer,
            currency=currency,
            amount=amount,
            offer=offer,
            price=price,
        )
        _record(trade, buyer, "")
    return trade

def open_trade_from_offer(offer, buyer, amount):
    offer = Offer.objects.get(pk=offer.pk)

    if not offer.is_active:
        raise InvalidMove("This offer is paused.")
    if buyer == offer.seller:
        raise NotAllowed("You can't buy from your own offer.")
    if amount < offer.min_amount or amount > offer.max_amount:
        raise InvalidMove(
            f"Amount must be between {offer.min_amount} and {offer.max_amount}."
        )
    if Trade.objects.filter(
        buyer=buyer,
        seller=offer.seller,
        status=Trade.Status.AWAITING_PAYMENT,
    ).exists():
        raise InvalidMove("You already have an unpaid trade with this seller.")

    return open_trade(
        offer.seller,
        buyer,
        offer.currency,
        amount,
        offer=offer,
        price=offer.price,
    )

def mark_paid(trade, user):
    with transaction.atomic():
        trade = _get_locked_trade(trade.pk)
        _check_allowed(trade, Trade.Status.PAID, user)
        old_status = trade.status
        trade.status = Trade.Status.PAID
        trade.save()
        _record(trade, user, old_status)
    return trade


def open_dispute(trade, user):
    with transaction.atomic():
        trade = _get_locked_trade(trade.pk)
        _check_allowed(trade, Trade.Status.DISPUTED, user)
        old_status = trade.status
        trade.status = Trade.Status.DISPUTED
        trade.save()
        _record(trade, user, old_status)
    return trade


def cancel_trade(trade, user):
    with transaction.atomic():
        trade = _get_locked_trade(trade.pk)
        _check_allowed(trade, Trade.Status.CANCELLED, user)
        seller_wallet = Wallet.objects.get(user=trade.seller, currency=trade.currency)
        unlock_funds(seller_wallet, trade.amount)
        old_status = trade.status
        trade.status = Trade.Status.CANCELLED
        trade.save()
        _record(trade, user, old_status)
    return trade


def release_trade(trade, user):
    with transaction.atomic():
        trade = _get_locked_trade(trade.pk)
        _check_allowed(trade, Trade.Status.RELEASED, user)
        seller_wallet = Wallet.objects.get(user=trade.seller, currency=trade.currency)
        buyer_wallet = Wallet.objects.get(user=trade.buyer, currency=trade.currency)
        release_funds(seller_wallet, buyer_wallet, trade.amount)
        old_status = trade.status
        trade.status = Trade.Status.RELEASED
        trade.save()
        _record(trade, user, old_status)
    return trade