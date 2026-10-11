import json
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from commerce import tests as cart_fixtures
from .models import ProductCollection, Product


class MerchandisingTests(TestCase):
    def setUp(self):
        cart_fixtures.CartTests.setUp(self)
        self.admin = get_user_model().objects.create_superuser("09123456895", "local-test-password")
        self.product = self.offer.variant.product
        self.row = ProductCollection.objects.create(title="Featured", slug="featured", is_published=True)
        self.row.products.add(self.product)

    def test_scheduling_and_stock_visibility_are_respected(self):
        path = "/api/v1/catalog/collections/featured/"
        self.assertEqual(len(self.client.get(path).json()["collection"]["products"]), 1)
        self.offer.status = "paused"
        self.offer.save()
        self.assertEqual(self.client.get(path).json()["collection"]["products"], [])
        self.row.starts_at = timezone.now() + timedelta(days=1)
        self.row.save()
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get("/api/v1/catalog/collections/").json()["collections"], [])
        self.assertEqual(self.client.get("/api/v1/catalog/sitemap/").json()["collections"], [])

    def test_bad_collection_update_is_atomic_and_role_restricted(self):
        path = f"/api/v1/operations/collections/{self.row.pk}/"
        data = {"title": "Changed", "product_ids": [999999], "reason": "Test invalid reference"}
        self.client.force_login(self.user)
        self.assertEqual(self.client.patch(path, json.dumps(data), content_type="application/json").status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.patch(path, json.dumps(data), content_type="application/json").status_code, 400)
        self.row.refresh_from_db()
        self.assertEqual(self.row.title, "Featured")
        self.assertEqual(self.row.products.count(), 1)
        data = {"starts_at": "2026-10-11T10:00:00", "reason": "Missing timezone"}
        self.assertEqual(self.client.patch(path, json.dumps(data), content_type="application/json").status_code, 400)

    def test_related_excludes_self_and_unpublished_items(self):
        Product.objects.create(title="Hidden", slug="hidden", category=self.product.category)
        result = self.client.get(f"/api/v1/catalog/products/{self.product.pk}/related/")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["products"], [])
