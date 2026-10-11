import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Category, Product, WishlistItem


class TrustApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("09123456301")
        self.other = get_user_model().objects.create_user("09123456302")
        category = Category.objects.create(name="Phones", slug="phones")
        self.product = Product.objects.create(title="Phone", slug="phone", category=category, status="published")

    def test_wishlist_is_private_and_repeat_add_does_not_duplicate(self):
        self.client.force_login(self.user)
        for _ in range(2):
            result = self.client.post("/api/v1/catalog/wishlist/", json.dumps({"product_id": self.product.pk}), content_type="application/json")
            self.assertEqual(result.status_code, 200)
        self.assertEqual(WishlistItem.objects.count(), 1)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/v1/catalog/wishlist/").json()["items"], [])
        self.client.delete(f"/api/v1/catalog/wishlist/{self.product.pk}/")
        self.assertEqual(WishlistItem.objects.count(), 1)

    def test_invalid_review_is_rejected_instead_of_server_error(self):
        self.client.force_login(self.user)
        result = self.client.post(f"/api/v1/catalog/reviews/{self.product.pk}/", json.dumps({"rating": 5, "title": None, "body": []}), content_type="application/json")
        self.assertEqual(result.status_code, 409)
