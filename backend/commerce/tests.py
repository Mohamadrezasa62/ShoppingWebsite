import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from catalog.models import Category, Offer, Product, Variant
from sellers.models import Seller

from .models import CartLine


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
