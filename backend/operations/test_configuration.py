import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from catalog.models import Category, CategoryFacet
from commerce.models import ShippingRule
from .models import AuditEvent


class ConfigurationTests(TestCase):
    def setUp(self):
        self.catalog = get_user_model().objects.create_user("09123456891", is_staff=True)
        self.catalog.groups.add(Group.objects.create(name="catalog_operator"))
        self.manager = get_user_model().objects.create_user("09123456892", is_staff=True)
        self.manager.groups.add(Group.objects.create(name="marketplace_manager"))
        self.category = Category.objects.create(name="Phones", slug="phones")

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def test_facet_query_operators_and_duplicate_choices_are_rejected(self):
        self.client.force_login(self.catalog)
        path = f"/api/v1/operations/categories/{self.category.pk}/facets/"
        for key in ("contains", "exact", "has_key", "123", "bad__key"):
            self.assertEqual(self.post(path, {"key": key, "label": "Filter", "choices": ["one"], "reason": "New filter"}).status_code, 400)
        self.assertEqual(self.post(path, {"key": "color", "label": "Color", "choices": ["red", "red"], "reason": "New filter"}).status_code, 400)
        self.assertEqual(self.post(path, {"key": "color", "label": "Color", "choices": ["red", "blue"], "reason": "New filter"}).status_code, 201)
        self.assertEqual(CategoryFacet.objects.count(), 1)
        self.assertTrue(AuditEvent.objects.filter(action="facet_saved").exists())

    def test_shipping_requires_marketplace_role_and_ordered_days(self):
        data = {"province": "Tehran", "fulfillment": "seller", "fee_toman": 10, "min_days": 3, "max_days": 1, "reason": "Shipping policy"}
        self.client.force_login(self.catalog)
        self.assertEqual(self.post("/api/v1/operations/shipping-rules/", data).status_code, 403)
        self.client.force_login(self.manager)
        self.assertEqual(self.post("/api/v1/operations/shipping-rules/", data).status_code, 400)
        self.assertFalse(ShippingRule.objects.exists())
        data["max_days"] = 4
        self.assertEqual(self.post("/api/v1/operations/shipping-rules/", data).status_code, 201)
        self.assertTrue(AuditEvent.objects.filter(action="shipping_rule_saved").exists())

    def test_brand_creation_rejects_duplicate_slug(self):
        self.client.force_login(self.catalog)
        data = {"name": "Brand", "slug": "brand", "reason": "Catalog brand"}
        self.assertEqual(self.post("/api/v1/operations/brands/", data).status_code, 201)
        data["name"] = "Other"
        self.assertEqual(self.post("/api/v1/operations/brands/", data).status_code, 400)
