import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase
from django.utils import timezone
from catalog.models import Category, Product, Variant, Offer
from sellers.models import Seller
from .models import Address, Cart, CartLine, Coupon, Order, ShippingRule
from .quotes import QUOTE_MAX_AGE, SALT


class QuoteApprovalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("09123456786")
        self.other = get_user_model().objects.create_user("09123456787")
        category = Category.objects.create(name="Phones", slug="phones")
        product = Product.objects.create(title="Phone", slug="phone", category=category, status="published")
        variant = Variant.objects.create(product=product, sku="phone-1")
        seller = Seller.objects.create(name="Store", status="approved")
        self.offer = Offer.objects.create(variant=variant, seller=seller, price_toman=10000, status="active", available_quantity=10)
        self.address = Address.objects.create(user=self.user, full_name="Buyer", phone="+989123456786", province="Tehran", city="Tehran", street="Private street", postal_code="1234567890")
        self.rule = ShippingRule.objects.create(province="Tehran", fee_toman=1500, min_days=2, max_days=4)
        self.cart = Cart.objects.create(user=self.user)
        self.line = CartLine.objects.create(cart=self.cart, offer=self.offer, quantity=2)
        self.client.force_login(self.user)

    def preview(self):
        response = self.client.get("/api/v1/commerce/quote/", {"address_id": self.address.pk})
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        return response.json()["quote"]

    def checkout(self, token, key=None):
        return self.client.post("/api/v1/commerce/checkout/", json.dumps({"address_id": self.address.pk, "idempotency_key": str(key or uuid4()), "quote_token": token}), content_type="application/json")

    def assert_unchanged(self):
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.reserved_quantity, 0)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(CartLine.objects.get(pk=self.line.pk).quantity, 2)

    def test_approved_amount_and_replay_after_expiry(self):
        quote = self.preview()
        token, key = quote["approval_token"], uuid4()
        decoded = signing.loads(token, salt=SALT)
        self.assertEqual(set(decoded), {"v", "user", "address", "digest"})
        self.assertNotIn(self.address.street, str(decoded))
        first = self.checkout(token, key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["order"]["grand_total_toman"], quote["estimated_total_toman"])
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp()+QUOTE_MAX_AGE+10):
            replay = self.checkout(token, key)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.json()["order"]["id"], replay.json()["order"]["id"])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(len(Order.objects.get().checkout_quote_digest), 64)

    def test_price_and_shipping_changes_require_reapproval(self):
        for model, field, value in [(self.offer, "price_toman", 12000), (self.rule, "fee_toman", 1800), (self.rule, "max_days", 6)]:
            token = self.preview()["approval_token"]
            setattr(model, field, value)
            model.save(update_fields=[field])
            response = self.checkout(token)
            self.assertEqual(response.json()["error"], "quote_changed")
            self.assert_unchanged()
        self.assertEqual(self.checkout(self.preview()["approval_token"]).status_code, 201)

    def test_address_cart_and_warranty_changes_require_reapproval(self):
        token = self.preview()["approval_token"]
        self.address.street = "New private street"
        self.address.save(update_fields=["street"])
        self.assertEqual(self.checkout(token).json()["error"], "quote_changed")
        self.assert_unchanged()
        token = self.preview()["approval_token"]
        self.offer.warranty = "New warranty"
        self.offer.save(update_fields=["warranty"])
        self.assertEqual(self.checkout(token).json()["error"], "quote_changed")
        token = self.preview()["approval_token"]
        self.line.quantity = 3
        self.line.save(update_fields=["quantity"])
        self.assertEqual(self.checkout(token).json()["error"], "quote_changed")
        self.assertEqual(Order.objects.count(), 0)

    def test_coupon_change_is_part_of_approval(self):
        coupon = Coupon.objects.create(code="SAVE", kind="fixed", value=1000, starts_at=timezone.now()-timedelta(days=1), ends_at=timezone.now()+timedelta(days=1), usage_limit=10, per_user_limit=2)
        token = self.preview()["approval_token"]
        self.cart.coupon = coupon
        self.cart.save(update_fields=["coupon"])
        self.assertEqual(self.checkout(token).json()["error"], "quote_changed")
        approved = self.preview()
        self.assertEqual(approved["discount_total_toman"], 1000)
        self.assertEqual(self.checkout(approved["approval_token"]).status_code, 201)

    def test_tampering_foreign_token_and_expiration(self):
        token = self.preview()["approval_token"]
        self.assertEqual(self.checkout(token+"broken").json()["error"], "invalid_quote")
        payload = signing.loads(token, salt=SALT)
        payload["user"] = self.other.pk
        self.assertEqual(self.checkout(signing.dumps(payload, salt=SALT)).json()["error"], "invalid_quote")
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp()+QUOTE_MAX_AGE+10):
            self.assertEqual(self.checkout(token).json()["error"], "quote_expired")
        self.assert_unchanged()

    def test_stock_is_not_guaranteed_and_unready_quotes_have_no_token(self):
        token = self.preview()["approval_token"]
        self.offer.available_quantity = 1
        self.offer.save(update_fields=["available_quantity"])
        self.assertEqual(self.checkout(token).json()["error"], "offer_unavailable")
        self.assertIsNone(self.preview()["approval_token"])
        self.assert_unchanged()

    def test_changed_token_cannot_reuse_existing_order_key(self):
        token = self.preview()["approval_token"]
        key = uuid4()
        self.assertEqual(self.checkout(token, key).status_code, 201)
        payload = signing.loads(token, salt=SALT)
        payload["digest"] = "0"*64
        response = self.checkout(signing.dumps(payload, salt=SALT), key)
        self.assertEqual(response.json()["error"], "idempotency_conflict")
        self.assertEqual(self.checkout(None, key).status_code, 400)
        self.assertEqual(Order.objects.count(), 1)

    def test_multi_seller_approval_matches_delivery_fees_and_line_prices(self):
        second = Seller.objects.create(name="Second store", status="approved")
        offer = Offer.objects.create(variant=self.offer.variant, seller=second, price_toman=12000, available_quantity=5, status="active")
        CartLine.objects.create(cart=self.cart, offer=offer, quantity=1)
        quote = self.preview()
        self.assertEqual(quote["shipping_total_toman"], 3000)
        self.assertEqual(len(quote["deliveries"]), 2)
        self.assertEqual(sum(line["line_total_toman"] for line in quote["lines"]), quote["item_subtotal_toman"])
        response = self.checkout(quote["approval_token"])
        self.assertEqual(response.status_code, 201)
        order = response.json()["order"]
        self.assertEqual(order["grand_total_toman"], quote["estimated_total_toman"])
        self.assertEqual(len(order["deliveries"]), 2)
