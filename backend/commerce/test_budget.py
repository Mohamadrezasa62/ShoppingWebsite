from uuid import uuid4
from django.test import TestCase
from . import test_promotions as fixtures
from .models import CartLine, Order
from .services import create_order, cancel_unpaid_order, CheckoutError


class CouponBudgetTests(TestCase):
    def setUp(self):
        fixtures.PromotionTests.setUp(self)
        self.coupon.usage_limit, self.coupon.per_user_limit = 100, 10
        self.coupon.save()
        self.offer.available_quantity, self.offer.reserved_quantity = 10, 0
        self.offer.save(update_fields=["available_quantity", "reserved_quantity"])

    def test_insufficient_budget_rolls_back_cart_stock_and_order(self):
        self.coupon.budget_toman = 2000
        self.coupon.save(update_fields=["budget_toman"])
        with self.assertRaises(CheckoutError) as caught:
            create_order(self.user, self.address.pk, uuid4())
        self.assertEqual(caught.exception.code, "coupon_budget_exceeded")
        self.assertFalse(Order.objects.exists())
        self.assertEqual(CartLine.objects.get().quantity, 2)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.reserved_quantity, 0)

    def test_pending_orders_reserve_budget_and_cancellation_releases_it(self):
        self.coupon.budget_toman = 6000
        self.coupon.save(update_fields=["budget_toman"])
        first, _ = create_order(self.user, self.address.pk, uuid4())
        self.cart.coupon = self.coupon
        self.cart.save(update_fields=["coupon"])
        CartLine.objects.create(cart=self.cart, offer=self.offer, quantity=2)
        create_order(self.user, self.address.pk, uuid4())
        self.cart.coupon = self.coupon
        self.cart.save(update_fields=["coupon"])
        CartLine.objects.create(cart=self.cart, offer=self.offer, quantity=1)
        with self.assertRaises(CheckoutError) as caught:
            create_order(self.user, self.address.pk, uuid4())
        self.assertEqual(caught.exception.code, "coupon_budget_exceeded")
        cancel_unpaid_order(first.pk, self.user)
        last, _ = create_order(self.user, self.address.pk, uuid4())
        self.assertEqual(last.discount_total_toman, 1500)
