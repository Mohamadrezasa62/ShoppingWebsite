from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import Address, Cart, CartLine, Coupon, CouponRedemption, OrderLine, ShippingRule
from .promotions import allocate_discount
from .returns import create_line_return, transition_return
from .services import CheckoutError, cancel_unpaid_order, create_order
from .tests import CartTests


class PromotionTests(TestCase):
    def setUp(self):
        CartTests.setUp(self)
        self.address = Address.objects.create(user=self.user, full_name="Buyer", phone=self.user.phone, province="Tehran", city="Tehran", street="Street", postal_code="1234567890")
        ShippingRule.objects.create(province="Tehran", fulfillment="seller", fee_toman=500, min_days=1, max_days=2)
        self.coupon = Coupon.objects.create(code="SAVE", kind="percent", value=15, usage_limit=1, per_user_limit=1, starts_at=timezone.now() - timedelta(days=1), ends_at=timezone.now() + timedelta(days=1))
        self.cart = Cart.objects.create(user=self.user, coupon=self.coupon)
        CartLine.objects.create(cart=self.cart, offer=self.offer, quantity=2)

    def test_discount_snapshot_and_cancel_releases_coupon_capacity(self):
        order, _ = create_order(self.user, self.address.pk, uuid4())
        self.assertEqual(order.discount_total_toman, 3000)
        self.assertEqual(order.grand_total_toman, 17500)
        self.assertEqual(OrderLine.objects.get().discount_toman, 3000)
        self.cart.refresh_from_db()
        self.cart.coupon = self.coupon
        self.cart.save()
        CartLine.objects.create(cart=self.cart, offer=self.offer, quantity=1)
        with self.assertRaises(CheckoutError):
            create_order(self.user, self.address.pk, uuid4())
        cancel_unpaid_order(order.pk, self.user)
        create_order(self.user, self.address.pk, uuid4())
        self.assertEqual(CouponRedemption.objects.count(), 2)

    def test_allocation_preserves_exact_total_and_stable_remainder(self):
        self.assertEqual(allocate_discount([1, 1, 1], 2), [1, 1, 0])
        self.assertEqual(sum(allocate_discount([100, 201, 333], 89)), 89)

    def test_rejected_return_does_not_duplicate_discount_rounding_remainder(self):
        order, _ = create_order(self.user, self.address.pk, uuid4())
        # A two-unit line with only one toman net-paid demonstrates rounding.
        line = order.deliveries.get().lines.get()
        OrderLine.objects.filter(pk=line.pk).update(discount_toman=line.line_total_toman - 1)
        order.status = "paid"
        order.save(update_fields=["status"])
        delivery = order.deliveries.get()
        delivery.status = "delivered"
        delivery.save(update_fields=["status"])
        first = create_line_return(self.user, delivery.pk, line.pk, 1, "First unit")
        second = create_line_return(self.user, delivery.pk, line.pk, 1, "Second unit")
        self.assertEqual((first.requested_amount_toman, second.requested_amount_toman), (0, 1))
        transition_return(first.pk, "rejected")
        replacement = create_line_return(self.user, delivery.pk, line.pk, 1, "Replacement request")
        self.assertEqual(replacement.requested_amount_toman, 0)
