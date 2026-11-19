from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from trades.models import Trade
from trades.services import (
    TradeError,
    cancel_trade,
    mark_paid,
    open_dispute,
    open_trade,
    release_trade,
)
from wallets.models import Wallet
from wallets.services import deposit


class TradeFlowTests(TestCase):
    def setUp(self):
        self.ama = User.objects.create_user("ama", password="test12345")
        self.kofi = User.objects.create_user("kofi", password="test12345")
        self.yaw = User.objects.create_user("yaw", password="test12345")
        self.support = User.objects.create_user(
            "support", password="test12345", is_staff=True
        )
        ama_wallet = Wallet.objects.create(user=self.ama, currency="USDT")
        deposit(ama_wallet, Decimal("100"))

    def wallet(self, user):
        return Wallet.objects.get(user=user, currency="USDT")

    def test_open_trade_locks_seller_coins(self):
        open_trade(self.ama, self.kofi, "USDT", Decimal("30"))
        self.assertEqual(self.wallet(self.ama).available, Decimal("70"))
        self.assertEqual(self.wallet(self.ama).locked, Decimal("30"))

    def test_failed_trade_creation_undoes_the_lock(self):
        with self.assertRaises(IntegrityError):
            open_trade(self.ama, self.ama, "USDT", Decimal("30"))
        self.assertEqual(self.wallet(self.ama).available, Decimal("100"))
        self.assertEqual(self.wallet(self.ama).locked, Decimal("0"))

    def test_full_trade_moves_coins_to_buyer(self):
        trade = open_trade(self.ama, self.kofi, "USDT", Decimal("30"))
        trade = mark_paid(trade, self.kofi)
        trade = release_trade(trade, self.ama)
        self.assertEqual(trade.status, Trade.Status.RELEASED)
        self.assertEqual(self.wallet(self.ama).locked, Decimal("0"))
        self.assertEqual(self.wallet(self.kofi).available, Decimal("30"))

    def test_cannot_release_before_payment(self):
        trade = open_trade(self.ama, self.kofi, "USDT", Decimal("30"))
        with self.assertRaises(TradeError):
            release_trade(trade, self.ama)

    def test_only_buyer_can_mark_paid(self):
        trade = open_trade(self.ama, self.kofi, "USDT", Decimal("30"))
        with self.assertRaises(TradeError):
            mark_paid(trade, self.ama)
        with self.assertRaises(TradeError):
            mark_paid(trade, self.yaw)

    def test_double_release_is_blocked(self):
        trade = open_trade(self.ama, self.kofi, "USDT", Decimal("30"))
        trade = mark_paid(trade, self.kofi)
        release_trade(trade, self.ama)
        with self.assertRaises(TradeError):
            release_trade(trade, self.ama)
        self.assertEqual(self.wallet(self.kofi).available, Decimal("30"))

    def test_support_can_settle_dispute_for_buyer(self):
        trade = open_trade(self.ama, self.kofi, "USDT", Decimal("30"))
        trade = mark_paid(trade, self.kofi)
        trade = open_dispute(trade, self.kofi)
        trade = release_trade(trade, self.support)
        self.assertEqual(trade.status, Trade.Status.RELEASED)
        self.assertEqual(self.wallet(self.kofi).available, Decimal("30"))

    # YOUR TURN: write these two tests yourself.
    def test_seller_cannot_cancel_after_payment(self):
        trade = open_trade(self.ama, self.kofi, "USDT", Decimal("30"))
        trade = mark_paid(trade, self.kofi)
        with self.assertRaises(TradeError):
            cancel_trade(trade, self.ama)

    def test_buyer_cancel_returns_coins_to_seller(self):
        trade = open_trade(self.ama, self.kofi, "USDT", Decimal("30"))
        trade =cancel_trade(trade, self.kofi)
        self.assertEqual(trade.status, Trade.Status.CANCELLED)
        self.assertEqual(self.wallet(self.ama).available, Decimal("100"))
        self.assertEqual(self.wallet(self.ama).locked, Decimal("0"))

    def test_every_move_is_recorded_with_its_actor(self):
        trade = open_trade(self.ama, self.kofi, "USDT", Decimal("30"))
        trade = mark_paid(trade, self.kofi)
        trade = release_trade(trade, self.ama)
        
        events = list(trade.events.order_by("pk"))
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0].actor, self.kofi)
        self.assertEqual(events[1].to_status, Trade.Status.PAID)
        self.assertEqual(events[2].actor, self.ama)
        self.assertEqual(events[2].from_status, Trade.Status.PAID)