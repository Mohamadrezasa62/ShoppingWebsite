from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from catalog.models import Category, Offer, Product, Variant
from commerce.models import Order, OrderDelivery, OrderLine
from sellers.models import Seller

from .models import LedgerEntry, PaymentAttempt
from .services import VerifiedCapture, record_verified_capture


class PaymentCaptureTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("09123456788")
        category = Category.objects.create(name="Phone", slug="phone")
        product = Product.objects.create(title="Phone", slug="phone", category=category)
        variant = Variant.objects.create(product=product, sku="phone-1")
        seller = Seller.objects.create(name="Seller")
        self.offer = Offer.objects.create(
            variant=variant, seller=seller, price_toman=10000,
            available_quantity=5, reserved_quantity=2,
        )
        self.order = Order.objects.create(
            user=user, idempotency_key=uuid4(), address_snapshot={},
            item_total_toman=20000, shipping_total_toman=5000,
            grand_total_toman=25000, expires_at=timezone.now() + timedelta(minutes=15),
        )
        delivery = OrderDelivery.objects.create(
            order=self.order, seller=seller, seller_name="Seller", fulfillment="seller",
            shipping_fee_toman=5000, min_days=2, max_days=4,
        )
        OrderLine.objects.create(
            delivery=delivery, offer=self.offer, product_title="Phone", variant_attributes={},
            seller_name="Seller", quantity=2, unit_price_toman=10000, line_total_toman=20000,
        )
        self.attempt = PaymentAttempt.objects.create(
            order=self.order, provider=PaymentAttempt.Provider.CARD,
            amount_toman=25000, idempotency_key=uuid4(),
        )

    def test_verified_capture_pays_once_and_commits_stock(self):
        result = VerifiedCapture("verified-1", 25000, "TOMAN")
        self.assertTrue(record_verified_capture(self.attempt.pk, result))
        self.assertTrue(record_verified_capture(self.attempt.pk, result))
        self.order.refresh_from_db()
        self.offer.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual((self.offer.available_quantity, self.offer.reserved_quantity), (3, 0))
        self.assertEqual(LedgerEntry.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.get().amount_toman, 25000)

    def test_wrong_amount_requires_review_and_preserves_reservation(self):
        self.assertFalse(record_verified_capture(self.attempt.pk, VerifiedCapture("verified-2", 20000, "TOMAN")))
        self.order.refresh_from_db()
        self.offer.refresh_from_db()
        self.attempt.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)
        self.assertEqual(self.attempt.status, PaymentAttempt.Status.REVIEW_REQUIRED)
        self.assertEqual(self.offer.reserved_quantity, 2)
        self.assertEqual(LedgerEntry.objects.get().amount_toman, 20000)

    def test_expired_order_records_received_money_for_review(self):
        self.order.expires_at = timezone.now() - timedelta(seconds=1)
        self.order.save(update_fields=["expires_at"])
        self.assertFalse(record_verified_capture(self.attempt.pk, VerifiedCapture("verified-3", 25000, "TOMAN")))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)
        self.assertEqual(LedgerEntry.objects.count(), 1)

    def test_invalid_capture_is_rejected_without_ledger(self):
        with self.assertRaises(ValueError):
            record_verified_capture(self.attempt.pk, VerifiedCapture("x", 25000, "IRR"))
        self.assertFalse(LedgerEntry.objects.exists())

    def test_methods_are_explicitly_disabled(self):
        response = self.client.get("/api/v1/payments/methods/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["available"], [])
        self.assertTrue(all(not method["enabled"] for method in response.json()["planned"]))
