from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.test import TestCase

from wallets.models import LedgerEntry, Wallet
from wallets.services import (
    InsufficientFunds,
    deposit,
    ledger_total,
    lock_funds,
    release_funds,
    unlock_funds,
)

from rest_framework.test import APITestCase

class WalletServiceTests(TestCase):
    def setUp(self):
        self.ama = User.objects.create_user("ama", password="test12345")
        self.kofi = User.objects.create_user("kofi", password="test12345")
        self.ama_wallet = Wallet.objects.create(user=self.ama, currency="USDT")
        self.kofi_wallet = Wallet.objects.create(user=self.kofi, currency="USDT")

    def assert_reconciled(self, wallet):
        wallet.refresh_from_db()
        self.assertEqual(wallet.available, ledger_total(wallet, "available"))
        self.assertEqual(wallet.locked, ledger_total(wallet, "locked"))

    def test_deposit_adds_to_available(self):
        wallet = deposit(self.ama_wallet, Decimal("100"))
        self.assertEqual(wallet.available, Decimal("100"))
        self.assert_reconciled(wallet)

    def test_deposit_rejects_zero(self):
        with self.assertRaises(ValueError):
            deposit(self.ama_wallet, Decimal("0"))

    def test_lock_moves_coins_from_available_to_locked(self):
        deposit(self.ama_wallet, Decimal("100"))
        wallet = lock_funds(self.ama_wallet, Decimal("40"))
        self.assertEqual(wallet.available, Decimal("60"))
        self.assertEqual(wallet.locked, Decimal("40"))
        self.assert_reconciled(wallet)

    def test_cannot_lock_more_than_available(self):
        deposit(self.ama_wallet, Decimal("100"))
        with self.assertRaises(InsufficientFunds):
            lock_funds(self.ama_wallet, Decimal("150"))

    def test_release_moves_locked_coins_to_buyer(self):
        deposit(self.ama_wallet, Decimal("100"))
        lock_funds(self.ama_wallet, Decimal("100"))
        seller, buyer = release_funds(self.ama_wallet, self.kofi_wallet, Decimal("100"))
        self.assertEqual(seller.locked, Decimal("0"))
        self.assertEqual(buyer.available, Decimal("100"))
        self.assert_reconciled(seller)
        self.assert_reconciled(buyer)

    def test_release_twice_fails(self):
        deposit(self.ama_wallet, Decimal("100"))
        lock_funds(self.ama_wallet, Decimal("100"))
        release_funds(self.ama_wallet, self.kofi_wallet, Decimal("100"))
        with self.assertRaises(InsufficientFunds):
            release_funds(self.ama_wallet, self.kofi_wallet, Decimal("100"))

    def test_database_blocks_negative_balance(self):
        self.ama_wallet.available = Decimal("-1")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.ama_wallet.save()

    def test_coins_are_never_created_or_destroyed(self):
        deposit(self.ama_wallet, Decimal("100"))
        lock_funds(self.ama_wallet, Decimal("60"))
        release_funds(self.ama_wallet, self.kofi_wallet, Decimal("60"))
        lock_funds(self.ama_wallet, Decimal("10"))
        unlock_funds(self.ama_wallet, Decimal("10"))
        total = LedgerEntry.objects.aggregate(total=Sum("amount"))["total"]
        self.assertEqual(total, Decimal("100"))

class WalletApiTests(APITestCase):
    def setUp(self):
        self.ama = User.objects.create_user("ama", password="test12345")
        self.kofi = User.objects.create_user("kofi", password="test12345")
        Wallet.objects.create(user=self.ama, currency="USDT")
        Wallet.objects.create(user=self.kofi, currency="BTC")

    def test_must_be_logged_in(self):
        response = self.client.get("/api/wallets/")
        self.assertEqual(response.status_code, 401)

    def test_user_sees_only_their_own_wallets(self):
        self.client.force_authenticate(user=self.ama)
        response = self.client.get("/api/wallets/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["currency"], "USDT")