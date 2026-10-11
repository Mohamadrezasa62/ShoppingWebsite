import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import ProductAlert
from .alerts import scan_alerts
from commerce.tests import CartTests
from operations.events import drain
from operations.models import Notification, OutboxEvent


class AlertTests(TestCase):
    def setUp(self):
        CartTests.setUp(self)
        self.other = get_user_model().objects.create_user("09123456498")
        self.client.force_login(self.user)
        self.product = self.offer.variant.product

    def subscribe(self, kind="price_drop", target=9000):
        return self.client.post("/api/v1/catalog/alerts/", json.dumps({"product_id": self.product.pk, "kind": kind, "target_price_toman": target}), content_type="application/json")

    def test_price_threshold_is_one_shot_and_rearm_has_new_generation(self):
        self.assertEqual(self.subscribe().status_code, 200)
        row = ProductAlert.objects.get()
        generation = row.generation
        self.assertEqual(scan_alerts()["fired"], 0)
        self.offer.price_toman = 8000
        self.offer.save()
        self.assertEqual(scan_alerts()["fired"], 1)
        self.assertEqual(scan_alerts()["fired"], 0)
        self.assertEqual(drain(), 1)
        self.assertEqual(Notification.objects.count(), 1)
        self.subscribe()
        row.refresh_from_db()
        self.assertNotEqual(row.generation, generation)
        self.assertEqual(scan_alerts()["fired"], 1)
        self.assertEqual(drain(), 1)
        self.assertEqual(Notification.objects.count(), 2)

    def test_reserved_stock_and_unsubscribe_before_dispatch(self):
        self.subscribe("back_in_stock", None)
        self.offer.reserved_quantity = self.offer.available_quantity
        self.offer.save()
        self.assertEqual(scan_alerts()["fired"], 0)
        self.offer.reserved_quantity = 0
        self.offer.save()
        self.assertEqual(scan_alerts()["fired"], 1)
        row = ProductAlert.objects.get()
        self.client.delete(f"/api/v1/catalog/alerts/{row.pk}/")
        drain()
        self.assertFalse(Notification.objects.exists())

    def test_alerts_are_private_and_validation_is_strict(self):
        self.assertEqual(self.subscribe(target=True).status_code, 400)
        self.subscribe()
        row = ProductAlert.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/v1/catalog/alerts/").json()["alerts"], [])
        self.assertEqual(self.client.delete(f"/api/v1/catalog/alerts/{row.pk}/").status_code, 404)

    def test_scan_cursor_reaches_subscriptions_after_first_batch(self):
        self.subscribe()
        first = scan_alerts(limit=1)
        self.assertEqual(first["scanned"], 1)
        self.assertEqual(scan_alerts(limit=1, after_id=first["last_id"])["scanned"], 0)
