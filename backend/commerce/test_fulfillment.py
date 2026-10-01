from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from catalog.models import Category, Offer, Product, Variant
from sellers.models import Seller

from .fulfillment import FulfillmentError, request_return, transition_delivery
from .models import Order, OrderDelivery, OrderLine, ReturnCase


class FulfillmentTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user("09123456789")
        category = Category.objects.create(name="Phone", slug="phone")
        product = Product.objects.create(title="Phone", slug="phone", category=category)
        variant = Variant.objects.create(product=product, sku="phone-1")
        seller = Seller.objects.create(name="Store")
        offer = Offer.objects.create(variant=variant, seller=seller, price_toman=10000, available_quantity=2)
        self.order = Order.objects.create(
            user=self.buyer, idempotency_key=uuid4(), address_snapshot={},
            item_total_toman=20000, shipping_total_toman=5000, grand_total_toman=25000,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        self.delivery = OrderDelivery.objects.create(
            order=self.order, seller=seller, seller_name="Store", fulfillment="seller",
            shipping_fee_toman=5000, min_days=2, max_days=4,
        )
        OrderLine.objects.create(
            delivery=self.delivery, offer=offer, product_title="Phone", variant_attributes={},
            seller_name="Store", quantity=2, unit_price_toman=10000, line_total_toman=20000,
        )

    def test_paid_delivery_tracks_shipment_and_return_cap(self):
        with self.assertRaises(FulfillmentError):
            transition_delivery(self.delivery.pk, OrderDelivery.Status.PACKING)
        self.order.status = Order.Status.PAID
        self.order.save(update_fields=["status"])
        transition_delivery(self.delivery.pk, OrderDelivery.Status.PACKING)
        with self.assertRaises(FulfillmentError):
            transition_delivery(self.delivery.pk, OrderDelivery.Status.SHIPPED)
        transition_delivery(self.delivery.pk, OrderDelivery.Status.SHIPPED, "TRACK-123")
        transition_delivery(self.delivery.pk, OrderDelivery.Status.DELIVERED)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.tracking_code, "TRACK-123")
        self.assertIsNotNone(self.delivery.delivered_at)
        with self.assertRaises(FulfillmentError):
            request_return(self.delivery.pk, self.buyer, "Damaged", 26000)
        case = request_return(self.delivery.pk, self.buyer, "Damaged", 20000)
        self.assertEqual(case.status, ReturnCase.Status.REQUESTED)
        self.assertEqual(case.requested_amount_toman, 20000)
