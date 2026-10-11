import json
from datetime import timedelta
from uuid import uuid4
from django.test import TestCase
from django.utils import timezone
from catalog.models import Offer, Product
from sellers.models import Seller
from .models import CartLine, Coupon, DeliverySlot, Order, ShippingMethod
from . import test_quotes as fixtures


class InvoiceTests(TestCase):
    setUp = fixtures.QuoteApprovalTests.setUp

    def create_order(self, methods=None, slots=None):
        params = {"address_id": self.address.pk}
        if methods is not None:
            params.update(shipping_methods=json.dumps(methods), shipping_slots=json.dumps(slots))
        quote = self.client.get("/api/v1/commerce/quote/", params).json()["quote"]
        payload = {"address_id": self.address.pk, "idempotency_key": str(uuid4()), "quote_token": quote["approval_token"]}
        if methods is not None:
            payload.update(shipping_methods=methods, shipping_slots=slots)
        response = self.client.post("/api/v1/commerce/checkout/", json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.order = Order.objects.get(pk=response.json()["order"]["id"])
        self.path = f"/api/v1/commerce/orders/{self.order.pk}/invoice/"

    def test_owner_only(self):
        self.create_order()
        self.client.logout()
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 401)
        self.assertIn("no-store", response["Cache-Control"])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.path).status_code, 404)
        self.other.is_staff = True
        self.other.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get(self.path).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.path).status_code, 405)

    def test_private_download_uses_original_snapshots(self):
        self.create_order()
        Product.objects.filter(pk=self.offer.variant.product_id).update(title="Changed title")
        Offer.objects.filter(pk=self.offer.pk).update(price_toman=99999)
        Seller.objects.filter(pk=self.offer.seller_id).update(name="Changed seller")
        self.address.street = "Changed address"
        self.address.save(update_fields=["street"])
        response = self.client.get(self.path)
        self.assertContains(response, "Phone")
        self.assertContains(response, "Private street")
        for changed in ["Changed title", "Changed seller", "Changed address", "99999"]:
            self.assertNotContains(response, changed)
        self.assertContains(response, "21500")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertIn("sandbox", response["Content-Security-Policy"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Content-Disposition"], f'attachment; filename="order-{self.order.pk}.html"')

    def test_untrusted_text_is_escaped(self):
        attack = '<script>alert("x")</script>'
        Product.objects.filter(pk=self.offer.variant.product_id).update(title=attack)
        self.offer.warranty = attack
        self.offer.save(update_fields=["warranty"])
        self.offer.variant.attributes = {attack: attack}
        self.offer.variant.save(update_fields=["attributes"])
        self.address.street = attack
        self.address.save(update_fields=["street"])
        self.create_order()
        response = self.client.get(self.path)
        self.assertNotContains(response, "<script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_multiple_sellers_coupon_and_bounded_queries(self):
        seller = Seller.objects.create(name="Second seller", status="approved")
        offer = Offer.objects.create(variant=self.offer.variant, seller=seller, price_toman=12000, available_quantity=5, status="active")
        CartLine.objects.create(cart=self.cart, offer=offer, quantity=1)
        coupon = Coupon.objects.create(code="SAVE", kind="fixed", value=1001, starts_at=timezone.now()-timedelta(days=1), ends_at=timezone.now()+timedelta(days=1), usage_limit=10, per_user_limit=2)
        self.cart.coupon = coupon
        self.cart.save(update_fields=["coupon"])
        self.create_order()
        with self.assertNumQueries(5):
            response = self.client.get(self.path)
        deliveries = response.context["deliveries"]
        self.assertEqual(len(deliveries), 2)
        self.assertEqual(sum(d.total_toman for d in deliveries), self.order.grand_total_toman)
        self.assertEqual(sum(row.discount_toman for d in deliveries for row in d.invoice_lines), 1001)
        self.assertContains(response, "Second seller")
        self.assertContains(response, "SAVE")

    def test_method_and_window_survive_configuration_edits(self):
        method = ShippingMethod.objects.create(rule=self.rule, code="express", label="Express original", fee_toman=3000, min_days=1, max_days=2)
        slot = DeliverySlot.objects.create(method=method, starts_at=timezone.now()+timedelta(days=3), ends_at=timezone.now()+timedelta(days=3, hours=2), capacity=2)
        key = f"{self.offer.seller_id}:seller"
        self.create_order({key: method.pk}, {key: slot.pk})
        method.label = "Changed method"
        method.save(update_fields=["label"])
        response = self.client.get(self.path)
        self.assertContains(response, "Express original")
        self.assertNotContains(response, "Changed method")
        delivery = response.context["deliveries"][0]
        self.assertEqual(delivery.delivery_window_start, slot.starts_at)
        self.assertContains(response, "بازهٔ انتخاب‌شده")
        self.assertNotContains(response, "برآورد ارسال هنگام ثبت سفارش")
        self.assertEqual(delivery.total_toman, 23000)
