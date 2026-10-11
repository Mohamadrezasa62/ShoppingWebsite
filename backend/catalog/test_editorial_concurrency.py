from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from django.test import RequestFactory, TransactionTestCase
from operations.events import process_event
from . import test_bulk_update as bulk_fixtures
from . import test_history as history_fixtures
from .history_api import history, record
from .models import Product, RecentProductView, BrowsingPreference


def race(first, second):
    gate = Barrier(2)
    def run(action):
        connections.close_all()
        try:
            gate.wait(timeout=10)
            return action()
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(run, (first, second)))


@skipUnless(connection.vendor == "postgresql", "Editorial product locks require PostgreSQL")
class EditorialConcurrencyTests(TransactionTestCase):
    setUp = bulk_fixtures.BulkUpdateTests.setUp
    source = bulk_fixtures.BulkUpdateTests.source
    submit = bulk_fixtures.BulkUpdateTests.submit

    def test_pending_file_cannot_overwrite_a_concurrent_individual_edit(self):
        job = self.submit()
        def edit():
            with transaction.atomic():
                product = Product.objects.select_for_update().get(pk=self.products[0].pk)
                product.title = "Individual editor change"
                product.save(update_fields=["title", "updated_at"])
        race(lambda: process_event(job.last_event_id), edit)
        self.products[0].refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(self.products[0].title, "Individual editor change")
        self.assertIn(job.status, ("failed", "succeeded"))
        if job.status == "failed":
            self.assertEqual(job.error["code"], "catalog_revision_conflict")
            self.products[1].refresh_from_db()
            self.assertTrue(self.products[1].title.startswith("Original"))


@skipUnless(connection.vendor == "postgresql", "Browsing preference revocation locks require PostgreSQL")
class HistoryConcurrencyTests(TransactionTestCase):
    setUp = history_fixtures.BrowsingHistoryTests.setUp
    product_with_offer = history_fixtures.BrowsingHistoryTests.product_with_offer

    def test_disabling_history_serializes_with_a_pending_view(self):
        BrowsingPreference.objects.create(user=self.user, enabled=True)
        def send(function, method, payload):
            import json
            request = getattr(RequestFactory(), method)("/history-test/", json.dumps(payload), content_type="application/json")
            request.user = get_user_model().objects.get(pk=self.user.pk)
            request._dont_enforce_csrf_checks = True
            return function(request).status_code
        results = race(lambda: send(record, "post", {"product_id": self.product.pk}), lambda: send(history, "patch", {"enabled": False}))
        self.assertEqual(results, [200, 200])
        self.assertFalse(BrowsingPreference.objects.get(user=self.user).enabled)
        self.assertFalse(RecentProductView.objects.filter(user=self.user).exists())
