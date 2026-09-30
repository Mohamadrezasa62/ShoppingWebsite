import json
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from catalog.models import Category, Offer, Product, Variant
from sellers.models import Seller

from .models import Address, CartLine, Order, OrderLine, ShippingRule
from .services import expire_order


class CartTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("09123456786")
        self.other = get_user_model().objects.create_user("09123456787")
        category = Category.objects.create(name="Phone", slug="phone")
        product = Product.objects.create(title="Example", slug="example", category=category, status=Product.Status.PUBLISHED)
        variant = Variant.objects.create(product=product, sku="example-1")
        seller = Seller.objects.create(name="Store", status=Seller.Status.APPROVED)
        self.offer = Offer.objects.create(variant=variant, seller=seller, price_toman=10000, status=Offer.Status.ACTIVE, available_quantity=4, reserved_quantity=1)

    def post(self, body):
        return self.client.post("/api/v1/commerce/cart/", json.dumps(body), content_type="application/json")

    def test_authenticated_cart_merges_lines_and_requotes(self):
        self.assertEqual(self.client.get("/api/v1/commerce/cart/").status_code, 401)
        self.client.force_login(self.user)
        self.assertEqual(self.post({"offer_id": self.offer.pk, "quantity": 1}).status_code, 201)
        response = self.post({"offer_id": self.offer.pk, "quantity": 2})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["cart"]["estimated_subtotal_toman"], 30000)
        self.assertTrue(response.json()["cart"]["can_checkout"])
        self.assertFalse(response.json()["cart"]["shipping_and_fees_calculated"])
        self.assertEqual(CartLine.objects.count(), 1)
        self.assertEqual(self.post({"offer_id": self.offer.pk, "quantity": 1}).status_code, 409)
        self.offer.price_toman = 12000
        self.offer.save()
        self.assertEqual(self.client.get("/api/v1/commerce/cart/").json()["cart"]["estimated_subtotal_toman"], 36000)

    def test_cart_is_private_and_stock_change_marks_line_unavailable(self):
        self.client.force_login(self.user)
        line_id = self.post({"offer_id": self.offer.pk, "quantity": 2}).json()["cart"]["lines"][0]["id"]
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/v1/commerce/cart/").json()["cart"]["lines"], [])
        self.assertEqual(self.client.patch(f"/api/v1/commerce/cart/lines/{line_id}/", json.dumps({"quantity": 1}), content_type="application/json").status_code, 404)
        self.client.force_login(self.user)
        self.offer.available_quantity = 2
        self.offer.save()
        cart = self.client.get("/api/v1/commerce/cart/").json()["cart"]
        self.assertFalse(cart["can_checkout"])
        self.assertFalse(cart["lines"][0]["available"])
        self.assertEqual(self.client.delete(f"/api/v1/commerce/cart/lines/{line_id}/").status_code, 200)
        self.assertEqual(CartLine.objects.count(), 0)

    def test_cart_mutations_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post("/api/v1/commerce/cart/", json.dumps({"offer_id": self.offer.pk, "quantity": 1}), content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_address_and_shipping_quote_group_seller_fees(self):
        self.client.force_login(self.user)
        address_data = {"full_name": "Buyer Name", "phone": "09123456786", "province": "Tehran", "city": "Tehran", "street": "Main street", "postal_code": "۱۲۳۴۵۶۷۸۹۰"}
        response = self.client.post("/api/v1/commerce/addresses/", json.dumps(address_data), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        address_id = response.json()["address"]["id"]
        self.assertEqual(response.json()["address"]["postal_code"], "1234567890")
        self.post({"offer_id": self.offer.pk, "quantity": 2})
        missing = self.client.get("/api/v1/commerce/quote/", {"address_id": address_id}).json()["quote"]
        self.assertFalse(missing["ready"])
        self.assertEqual(len(missing["missing_shipping_rules"]), 1)
        ShippingRule.objects.create(province="Tehran", fulfillment="seller", fee_toman=15000, min_days=2, max_days=4)
        quote = self.client.get("/api/v1/commerce/quote/", {"address_id": address_id}).json()["quote"]
        self.assertTrue(quote["ready"])
        self.assertEqual(quote["item_subtotal_toman"], 20000)
        self.assertEqual(quote["shipping_total_toman"], 15000)
        self.assertEqual(quote["estimated_total_toman"], 35000)
        self.assertFalse(quote["is_final"])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/v1/commerce/quote/", {"address_id": address_id}).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/v1/commerce/addresses/{address_id}/").status_code, 404)

    def test_checkout_snapshots_totals_reserves_and_expires_idempotently(self):
        self.client.force_login(self.user)
        address = Address.objects.create(user=self.user, full_name="Buyer Name", phone="+989123456786", province="Tehran", city="Tehran", street="Main street", postal_code="1234567890")
        ShippingRule.objects.create(province="Tehran", fulfillment="seller", fee_toman=15000, min_days=2, max_days=4)
        self.post({"offer_id": self.offer.pk, "quantity": 2})
        key = str(uuid4())
        payload = {"address_id": address.pk, "idempotency_key": key}
        response = self.client.post("/api/v1/commerce/checkout/", json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        order_id = response.json()["order"]["id"]
        self.assertEqual(response.json()["order"]["grand_total_toman"], 35000)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.reserved_quantity, 3)
        self.assertEqual(self.client.get("/api/v1/commerce/cart/").json()["cart"]["lines"], [])
        self.assertEqual(self.client.post("/api/v1/commerce/checkout/", json.dumps(payload), content_type="application/json").status_code, 200)
        self.assertEqual(Order.objects.count(), 1)
        self.offer.price_toman = 20000
        self.offer.save()
        self.assertEqual(OrderLine.objects.get().unit_price_toman, 10000)
        self.assertEqual(self.client.get(f"/api/v1/commerce/orders/{order_id}/").json()["order"]["grand_total_toman"], 35000)
        order = Order.objects.get(pk=order_id)
        self.assertFalse(expire_order(order.pk, order.expires_at - timedelta(seconds=1)))
        self.assertTrue(expire_order(order.pk, order.expires_at + timedelta(seconds=1)))
        self.assertFalse(expire_order(order.pk, order.expires_at + timedelta(seconds=2)))
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.reserved_quantity, 1)
        self.assertEqual(Order.objects.get(pk=order_id).status, Order.Status.EXPIRED)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/api/v1/commerce/orders/{order_id}/").status_code, 404)

    def test_checkout_failure_keeps_cart_and_stock(self):
        self.client.force_login(self.user)
        address = Address.objects.create(user=self.user, full_name="Buyer Name", phone="+989123456786", province="Tehran", city="Tehran", street="Main street", postal_code="1234567890")
        self.post({"offer_id": self.offer.pk, "quantity": 2})
        response = self.client.post("/api/v1/commerce/checkout/", json.dumps({"address_id": address.pk, "idempotency_key": str(uuid4())}), content_type="application/json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "shipping_unavailable")
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.reserved_quantity, 1)
        self.assertEqual(CartLine.objects.count(), 1)
        self.assertEqual(Order.objects.count(), 0)
