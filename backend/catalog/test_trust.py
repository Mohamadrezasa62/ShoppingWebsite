from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from commerce.models import Order, OrderDelivery, OrderLine
from sellers.models import Seller

from .models import Category, Offer, Product, ProductReview, Variant, WishlistItem
from .trust import ReviewError, add_wishlist_item, submit_review


class TrustTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user("09123456780")
        category = Category.objects.create(name="Phones", slug="phones")
        self.product = Product.objects.create(title="Phone", slug="phone", category=category)
        variant = Variant.objects.create(product=self.product, sku="phone-1")
        seller = Seller.objects.create(name="Store")
        offer = Offer.objects.create(variant=variant, seller=seller, price_toman=10000)
        self.order = Order.objects.create(
            user=self.buyer, idempotency_key=uuid4(), address_snapshot={},
            item_total_toman=10000, shipping_total_toman=0, grand_total_toman=10000,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        self.delivery = OrderDelivery.objects.create(
            order=self.order, seller=seller, seller_name="Store", fulfillment="seller",
            shipping_fee_toman=0, min_days=1, max_days=2,
        )
        OrderLine.objects.create(
            delivery=self.delivery, offer=offer, product_title="Phone", variant_attributes={},
            seller_name="Store", quantity=1, unit_price_toman=10000, line_total_toman=10000,
        )

    def test_review_requires_delivered_paid_purchase(self):
        with self.assertRaises(ReviewError):
            submit_review(self.buyer, self.product, 5, "Great", "Works well")
        self.order.status = Order.Status.PAID
        self.order.save(update_fields=["status"])
        self.delivery.status = OrderDelivery.Status.DELIVERED
        self.delivery.save(update_fields=["status"])
        review = submit_review(self.buyer, self.product, 5, "Great", "Works well")
        self.assertEqual(review.status, ProductReview.Status.PENDING)
        self.assertTrue(review.verified_purchase)
        with self.assertRaises(ReviewError):
            submit_review(self.buyer, self.product, 4, "Again", "Second review")

    def test_wishlist_add_is_idempotent(self):
        first = add_wishlist_item(self.buyer, self.product)
        self.assertEqual(first.pk, add_wishlist_item(self.buyer, self.product).pk)
        self.assertEqual(WishlistItem.objects.count(), 1)
