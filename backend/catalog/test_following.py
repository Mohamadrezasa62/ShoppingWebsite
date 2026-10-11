import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from catalog import tests as catalog_fixtures
from .models import FollowSubscription


class FollowingTests(TestCase):
    def setUp(self):
        catalog_fixtures.PublicCatalogTests.setUp(self)
        self.user = get_user_model().objects.create_user("09123456911")
        self.other = get_user_model().objects.create_user("09123456912")
        self.client.force_login(self.user)

    def follow(self, kind, pk):
        return self.client.post("/api/v1/catalog/following/", json.dumps({"kind": kind, "target_id": pk}), content_type="application/json")

    def test_following_is_private_idempotent_and_not_marketing_consent(self):
        first = self.follow("brand", self.brand.pk)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.follow("brand", self.brand.pk).json(), first.json())
        self.assertEqual(FollowSubscription.objects.count(), 1)
        self.assertEqual(self.client.get("/api/v1/catalog/feed/").json()["products"][0]["id"], self.product.pk)
        self.assertEqual(self.client.get("/api/v1/catalog/feed/")["Cache-Control"], "no-store")
        from operations.models import OutboxEvent, Notification
        self.assertFalse(OutboxEvent.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/v1/catalog/following/").json()["following"], [])
        self.assertEqual(self.client.get("/api/v1/catalog/feed/").json()["products"], [])
        self.assertEqual(self.client.delete(f"/api/v1/catalog/following/{first.json()['following']['id']}/").status_code, 404)

    def test_seller_and_brand_follow_do_not_duplicate_cards_and_unfollow_updates_feed(self):
        brand = self.follow("brand", self.brand.pk).json()["following"]
        seller = self.follow("seller", self.seller_a.pk).json()["following"]
        feed = self.client.get("/api/v1/catalog/feed/").json()
        self.assertEqual(len(feed["products"]), 1)
        self.assertEqual(feed["products"][0]["price_toman"], 90000)
        self.client.delete(f"/api/v1/catalog/following/{brand['id']}/")
        self.client.delete(f"/api/v1/catalog/following/{seller['id']}/")
        self.assertEqual(self.client.get("/api/v1/catalog/feed/").json()["products"], [])

    def test_unavailable_or_suspended_targets_cannot_be_followed_and_leave_feed(self):
        self.follow("seller", self.seller_a.pk)
        self.seller_a.status = "suspended"
        self.seller_a.save(update_fields=["status"])
        self.assertEqual(self.follow("seller", self.seller_a.pk).status_code, 404)
        self.assertEqual(self.client.get("/api/v1/catalog/feed/").json()["products"], [])
        self.brand.is_active = False
        self.brand.save(update_fields=["is_active"])
        self.assertEqual(self.follow("brand", self.brand.pk).status_code, 404)

    def test_invalid_requests_and_csrf_do_not_create_follows(self):
        for kind, pk in [("unknown", 1), ("brand", True), ("seller", -1), ([], 1)]:
            self.assertEqual(self.follow(kind, pk).status_code, 400)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post("/api/v1/catalog/following/", "{}", content_type="application/json").status_code, 403)
        self.assertFalse(FollowSubscription.objects.exists())

    def test_export_contains_only_owned_follow_targets(self):
        self.follow("brand", self.brand.pk)
        FollowSubscription.objects.create(user=self.other, seller=self.seller_b)
        exported = self.client.get("/api/v1/auth/export/").json()["following"]
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["brand_id"], self.brand.pk)
        self.assertIsNone(exported[0]["seller_id"])

    def test_limit_still_allows_repeating_an_existing_follow(self):
        from .models import Brand
        brands = Brand.objects.bulk_create([Brand(name=f"Follow fixture {n}", slug=f"follow-fixture-{n}") for n in range(99)])
        FollowSubscription.objects.bulk_create([FollowSubscription(user=self.user, brand=brand) for brand in brands])
        self.assertEqual(self.follow("brand", self.brand.pk).status_code, 200)
        self.assertEqual(self.follow("brand", self.brand.pk).status_code, 200)
        self.assertEqual(self.follow("seller", self.seller_a.pk).status_code, 409)
        self.assertEqual(FollowSubscription.objects.count(), 100)
