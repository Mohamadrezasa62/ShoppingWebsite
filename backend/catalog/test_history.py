import json
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone
from accounts.closure import request_closure, decide_closure
from .models import BrowsingPreference, RecentProductView, Category, Product, Variant, Offer
from .tasks import purge_expired_history
from sellers.models import Seller


class BrowsingHistoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("09123456401")
        self.other = get_user_model().objects.create_user("09123456402")
        self.category = Category.objects.create(name="Phones", slug="phones")
        self.seller = Seller.objects.create(name="Store", status="approved")
        self.product = self.product_with_offer(1)
        self.client.force_login(self.user)

    def product_with_offer(self, number):
        product = Product.objects.create(title=f"Phone {number}", slug=f"phone-{number}", category=self.category, status="published")
        variant = Variant.objects.create(product=product, sku=f"PHONE-{number}")
        Offer.objects.create(variant=variant, seller=self.seller, price_toman=100, available_quantity=5, status="active")
        return product

    def enable(self, enabled=True):
        return self.client.patch("/api/v1/catalog/history/", json.dumps({"enabled": enabled}), content_type="application/json")

    def record(self, product=None):
        return self.client.post("/api/v1/catalog/history/views/", json.dumps({"product_id": (product or self.product).pk}), content_type="application/json")

    def test_default_off_opt_in_dedup_and_private_clear(self):
        self.assertFalse(self.client.get("/api/v1/catalog/history/").json()["enabled"])
        self.assertFalse(self.record().json()["recorded"])
        self.assertFalse(RecentProductView.objects.exists())
        self.assertEqual(self.enable().status_code, 200)
        self.assertTrue(self.record().json()["recorded"])
        self.assertTrue(self.record().json()["recorded"])
        self.assertEqual(RecentProductView.objects.count(), 1)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/v1/catalog/history/").json()["products"], [])
        self.assertEqual(self.client.delete("/api/v1/catalog/history/").status_code, 200)
        self.assertEqual(RecentProductView.objects.count(), 1)
        self.client.force_login(self.user)
        cleared = self.client.delete("/api/v1/catalog/history/").json()
        self.assertTrue(cleared["enabled"])
        self.assertFalse(RecentProductView.objects.exists())

    def test_disable_removes_all_history_and_stops_stale_record(self):
        self.enable()
        self.record()
        result = self.enable(False).json()
        self.assertFalse(result["enabled"])
        self.assertEqual(result["products"], [])
        self.assertFalse(self.record().json()["recorded"])
        self.assertFalse(RecentProductView.objects.exists())
        self.assertFalse(self.client.get("/api/v1/auth/me/").json()["browsing_history_enabled"])

    def test_history_is_bounded_recency_ordered_and_unavailable_products_hidden(self):
        self.enable()
        products = [self.product] + [self.product_with_offer(n) for n in range(2, 52)]
        RecentProductView.objects.bulk_create([RecentProductView(user=self.user, product=product, viewed_at=timezone.now()-timedelta(minutes=n+1)) for n, product in enumerate(products)])
        newest = products[-1]
        self.record(newest)
        self.assertEqual(RecentProductView.objects.count(), 50)
        result = self.client.get("/api/v1/catalog/history/").json()["products"]
        self.assertEqual(result[0]["id"], newest.pk)
        newest.status = "draft"
        newest.save(update_fields=["status"])
        self.assertEqual(self.record(newest).status_code, 404)
        self.assertNotIn(newest.pk, [row["id"] for row in self.client.get("/api/v1/catalog/history/").json()["products"]])

    def test_expired_rows_excluded_from_reads_exports_and_purged(self):
        self.enable()
        RecentProductView.objects.create(user=self.user, product=self.product, viewed_at=timezone.now()-timedelta(days=31))
        self.assertEqual(self.client.get("/api/v1/catalog/history/").json()["products"], [])
        self.assertEqual(self.client.get("/api/v1/auth/export/").json()["recently_viewed"], [])
        self.assertEqual(purge_expired_history(), 1)
        self.record()
        self.assertEqual(purge_expired_history(), 0)
        exported = self.client.get("/api/v1/auth/export/").json()
        self.assertTrue(exported["browsing_history_enabled"])
        self.assertEqual(exported["recently_viewed"][0]["product_id"], self.product.pk)

    def test_authenticated_csrf_and_strict_mutation_inputs(self):
        path = "/api/v1/catalog/history/"
        self.client.logout()
        self.assertEqual(self.client.get(path).status_code, 401)
        self.client.force_login(self.user)
        for value in [None, 1, "true"]:
            self.assertEqual(self.client.patch(path, json.dumps({"enabled": value}), content_type="application/json").status_code, 400)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.patch(path, json.dumps({"enabled": True}), content_type="application/json").status_code, 403)
        self.assertEqual(client.delete(path).status_code, 403)
        self.assertEqual(client.post(path+"views/", json.dumps({"product_id": self.product.pk}), content_type="application/json").status_code, 403)

    def test_account_deactivation_removes_browsing_history_atomically(self):
        self.enable()
        self.record()
        admin = get_user_model().objects.create_user("09123456403", is_staff=True)
        case = request_closure(self.user, "Close account")
        with patch("accounts.closure.audit", side_effect=RuntimeError("Audit outage")):
            with self.assertRaises(RuntimeError):
                decide_closure(case.pk, "completed", admin, "Verified request")
        self.assertTrue(BrowsingPreference.objects.get(user=self.user).enabled)
        self.assertTrue(RecentProductView.objects.filter(user=self.user).exists())
        decide_closure(case.pk, "completed", admin, "Verified request")
        self.assertFalse(BrowsingPreference.objects.get(user=self.user).enabled)
        self.assertFalse(RecentProductView.objects.filter(user=self.user).exists())
