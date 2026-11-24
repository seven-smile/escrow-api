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

from rest_framework.test import APITestCase
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
        trade = mark_paid(trade, self.kofi)
        with self.assertRaises(TradeError):
            mark_paid(trade, self.yaw)

    def test_buyer_cannot_release(self):
            trade = open_trade(self.ama, self.kofi, "USDT", Decimal("30"))
            with self.assertRaises(TradeError):
                mark_paid(trade, self.ama)
            with self.assertRaises(TradeError):
                release_trade(trade, self.kofi)

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

    def test_support_decision_is_recorded(self):
        trade = open_trade(self.ama, self.kofi, "USDT" ,Decimal("30"))
        trade = mark_paid(trade, self.kofi)
        trade = open_dispute(trade, self.kofi)
        trade = release_trade(trade, self.support)

        events = list(trade.events.order_by("pk"))
        self.assertEqual(events[-1].actor, self.support)
        self.assertEqual(events[-1].to_status, Trade.Status.RELEASED)
class TradeApiTests(APITestCase):
    def setUp(self):
        self.ama = User.objects.create_user("ama", password="test12345")
        self.kofi = User.objects.create_user("kofi", password="test12345")
        self.yaw = User.objects.create_user("yaw", password="test12345")
        ama_wallet = Wallet.objects.create(user=self.ama, currency="USDT")
        deposit(ama_wallet, Decimal("100"))
        self.trade = open_trade(self.ama, self.kofi, "USDT", Decimal("30"))

    def url(self, action):
        return f"/api/trades/{self.trade.pk}/{action}/"

    def test_buyer_can_mark_paid(self):
        self.client.force_authenticate(user=self.kofi)
        response = self.client.post(self.url("mark-paid"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "paid")

    def test_buyer_cannot_release_gets_403(self):
        mark_paid(self.trade, self.kofi)
        self.client.force_authenticate(user=self.kofi)
        response = self.client.post(self.url("release"))
        self.assertEqual(response.status_code, 403)

    def test_release_before_payment_gets_409(self):
        self.client.force_authenticate(user=self.ama)
        response = self.client.post(self.url("release"))
        self.assertEqual(response.status_code, 409)

    def test_stranger_gets_404(self):
        self.client.force_authenticate(user=self.yaw)
        response = self.client.post(self.url("mark-paid"))
        self.assertEqual(response.status_code, 404)

    def test_my_trades_only_shows_my_trades(self):
        self.client.force_authenticate(user=self.yaw)
        response = self.client.get("/api/trades/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_seller_can_release_after_payment(self):
        mark_paid(self.trade, self.kofi)
        self.client.force_authenticate(user=self.ama)
        response = self.client.post(self.url("release"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "released")
