import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from catalog.models import Category, Product, Variant
from .models import AuditEvent


class CatalogManagementTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("09123456100", is_staff=True)
        self.staff.groups.add(Group.objects.create(name="catalog_operator"))
        self.buyer = get_user_model().objects.create_user("09123456101")
        self.category = Category.objects.create(name="Phones", slug="phones")

    def test_create_publish_and_variant_are_audited(self):
        self.client.force_login(self.staff)
        response = self.client.post("/api/v1/operations/products/", json.dumps({"title": "Phone", "slug": "phone", "category_id": self.category.pk, "reason": "New catalog item"}), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        product_id = response.json()["product"]["id"]
        response = self.client.patch(f"/api/v1/operations/products/{product_id}/", json.dumps({"status": "published", "reason": "Catalog approved"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Product.objects.get().status, "published")
        response = self.client.post(f"/api/v1/operations/products/{product_id}/variants/", json.dumps({"sku": "P-1", "attributes": {"color": "black"}, "reason": "Variant approved"}), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Variant.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 3)

    def test_buyer_forbidden_and_invalid_update_not_saved(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get("/api/v1/operations/products/").status_code, 403)
        product = Product.objects.create(title="Original", slug="original", category=self.category)
        self.client.force_login(self.staff)
        response = self.client.patch(f"/api/v1/operations/products/{product.pk}/", json.dumps({"title": "Changed", "status": "bad", "reason": "Bad request"}), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        product.refresh_from_db()
        self.assertEqual(product.title, "Original")
        self.assertFalse(AuditEvent.objects.exists())
