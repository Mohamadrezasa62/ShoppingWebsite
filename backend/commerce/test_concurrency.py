from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase
from catalog.models import Category, Offer, Product, Variant
from sellers.models import Seller
from .models import Address, Cart, CartLine, Order, ShippingRule
from .services import CheckoutError, create_order


@skipUnless(connection.vendor == "postgresql", "Row-lock concurrency requires PostgreSQL")
class CheckoutConcurrencyTests(TransactionTestCase):
    def setUp(self):
        category = Category.objects.create(name="Phones", slug="phones")
        product = Product.objects.create(title="Phone", slug="phone", category=category, status="published")
        variant = Variant.objects.create(product=product, sku="PHONE-1")
        seller = Seller.objects.create(name="Seller", status="approved")
        self.offer = Offer.objects.create(variant=variant, seller=seller, price_toman=100, available_quantity=1, status="active")
        ShippingRule.objects.create(province="Tehran", fulfillment="seller", fee_toman=10, min_days=1, max_days=2)
        self.inputs = []
        for index in (1, 2):
            user = get_user_model().objects.create_user(f"0912345650{index}")
            address = Address.objects.create(user=user, full_name="Buyer", phone=user.phone, province="Tehran", city="Tehran", street="Street", postal_code="1234567890")
            cart = Cart.objects.create(user=user)
            CartLine.objects.create(cart=cart, offer=self.offer, quantity=1)
            self.inputs.append((user.pk, address.pk, uuid4()))

    @staticmethod
    def checkout(args):
        connections.close_all()
        try:
            user_id, address_id, key = args
            user = get_user_model().objects.get(pk=user_id)
            try:
                return create_order(user, address_id, key)[0].pk
            except CheckoutError as error:
                return error.code
        finally:
            connections.close_all()

    def test_two_buyers_cannot_reserve_last_unit(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.checkout, self.inputs))
        self.assertEqual(sum(isinstance(value, int) for value in results), 1)
        self.assertIn("offer_unavailable", results)
        self.assertEqual(Order.objects.count(), 1)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.reserved_quantity, 1)

    def test_duplicate_checkout_creates_one_order(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.checkout, [self.inputs[0], self.inputs[0]]))
        self.assertEqual(results[0], results[1])
        self.assertIsInstance(results[0], int)
        self.assertEqual(Order.objects.count(), 1)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.reserved_quantity, 1)

    def test_last_coupon_capacity_is_not_oversubscribed(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import Coupon, CouponRedemption
        coupon = Coupon.objects.create(code="LAST", kind="fixed", value=10, usage_limit=1, per_user_limit=1, starts_at=timezone.now() - timedelta(days=1), ends_at=timezone.now() + timedelta(days=1))
        # Separate offer locks ensure the shared coupon is the contention point.
        second_variant = Variant.objects.create(product=self.offer.variant.product, sku="PHONE-2")
        second_offer = Offer.objects.create(variant=second_variant, seller=self.offer.seller, price_toman=100, available_quantity=1, status="active")
        for index, (user_id, _, _) in enumerate(self.inputs):
            cart = Cart.objects.get(user_id=user_id)
            cart.coupon = coupon
            cart.save()
            if index:
                cart.lines.update(offer=second_offer)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.checkout, self.inputs))
        self.assertEqual(sum(isinstance(value, int) for value in results), 1)
        self.assertIn("coupon_usage_exceeded", results)
        self.assertEqual(CouponRedemption.objects.count(), 1)

    def test_shared_coupon_budget_is_not_oversubscribed(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import Coupon
        coupon = Coupon.objects.create(code="BUDGET", kind="fixed", value=10, budget_toman=10, usage_limit=100, per_user_limit=1, starts_at=timezone.now()-timedelta(days=1), ends_at=timezone.now()+timedelta(days=1))
        variant = Variant.objects.create(product=self.offer.variant.product, sku="BUDGET-SECOND")
        second_offer = Offer.objects.create(variant=variant, seller=self.offer.seller, price_toman=100, available_quantity=1, status="active")
        for index, (user_id, _, _) in enumerate(self.inputs):
            cart = Cart.objects.get(user_id=user_id)
            cart.coupon = coupon
            cart.save(update_fields=["coupon"])
            if index:
                cart.lines.update(offer=second_offer)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.checkout, self.inputs))
        self.assertEqual(sum(isinstance(value, int) for value in results), 1)
        self.assertIn("coupon_budget_exceeded", results)
        self.assertEqual(Order.objects.get().discount_total_toman, 10)
