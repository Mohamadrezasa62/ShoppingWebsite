import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from catalog import test_trust
from .models import SellerMembership, SellerReview
from operations.models import AuditEvent


class SellerReviewTests(TestCase):
    def setUp(self):
        test_trust.TrustTests.setUp(self)
        self.order.status = "paid"
        self.order.save(update_fields=["status"])
        self.delivery.status = "delivered"
        self.delivery.save(update_fields=["status"])
        self.seller = self.delivery.seller
        self.seller.status = "approved"
        self.seller.save(update_fields=["status"])
        self.other = get_user_model().objects.create_user("09123456399")
        self.staff = get_user_model().objects.create_user("09123456398", is_staff=True)
        self.staff.groups.add(Group.objects.get_or_create(name="support_agent")[0])
        self.payload = {"delivery_id": self.delivery.pk, "rating": 5, "body": "Reliable delivery"}
        self.client.force_login(self.buyer)

    def post(self, data=None):
        return self.client.post("/api/v1/seller/reviews/", json.dumps(data or self.payload), content_type="application/json")

    def test_verified_delivery_is_idempotent_and_private(self):
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post({**self.payload, "rating": 3}).status_code, 409)
        self.assertEqual(SellerReview.objects.count(), 1)
        self.assertEqual(self.client.get(f"/api/v1/seller/public/{self.seller.pk}/reviews/").json()["count"], 0)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/v1/seller/reviews/").json()["reviews"], [])
        self.assertEqual(self.post().status_code, 404)

    def test_not_delivered_or_unpaid_and_own_store_are_rejected(self):
        self.delivery.status = "packing"
        self.delivery.save(update_fields=["status"])
        self.assertEqual(self.post().status_code, 409)
        self.delivery.status = "delivered"
        self.delivery.save(update_fields=["status"])
        self.order.status = "pending_payment"
        self.order.save(update_fields=["status"])
        self.assertEqual(self.post().status_code, 409)
        self.order.status = "paid"
        self.order.save(update_fields=["status"])
        SellerMembership.objects.create(user=self.buyer, seller=self.seller, role="owner")
        self.assertEqual(self.post().status_code, 409)
        self.assertFalse(SellerReview.objects.exists())

    def test_moderation_publication_hiding_export_and_rollback(self):
        self.post()
        row = SellerReview.objects.get()
        url = f"/api/v1/operations/seller-reviews/{row.pk}/decision/"
        self.assertEqual(self.client.post(url, json.dumps({"status": "published", "reason": "Checked purchase"}), content_type="application/json").status_code, 403)
        self.client.force_login(self.staff)
        with patch("sellers.review_api._audit", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.post(url, json.dumps({"status": "published", "reason": "Checked purchase"}), content_type="application/json")
        row.refresh_from_db()
        self.assertEqual(row.status, "pending")
        self.assertEqual(self.client.post(url, json.dumps({"status": "published", "reason": "Checked purchase"}), content_type="application/json").status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(action="seller_review_moderated").exists())
        self.client.logout()
        data = self.client.get(f"/api/v1/seller/public/{self.seller.pk}/reviews/").json()
        self.assertEqual(data["average_rating"], 5)
        self.assertEqual(set(data["reviews"][0]), {"rating", "body", "verified_purchase"})
        self.seller.status = "suspended"
        self.seller.save(update_fields=["status"])
        self.assertEqual(self.client.get(f"/api/v1/seller/public/{self.seller.pk}/reviews/").status_code, 404)
        self.client.force_login(self.buyer)
        self.assertEqual(len(self.client.get("/api/v1/auth/export/").json()["seller_reviews"]), 1)

    def test_csrf_and_invalid_fields(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.buyer)
        self.assertEqual(csrf.post("/api/v1/seller/reviews/", json.dumps(self.payload), content_type="application/json").status_code, 403)
        for change in ({"rating": True}, {"body": "x\x00y"}, {"delivery_id": "1"}, {"status": "published"}):
            self.assertEqual(self.post({**self.payload, **change}).status_code, 400)
