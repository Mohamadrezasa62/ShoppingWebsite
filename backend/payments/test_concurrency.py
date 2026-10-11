from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from django.db import connection, connections
from django.test import TransactionTestCase
from .tests import PaymentCaptureTests
from .models import LedgerEntry
from .services import VerifiedCapture, record_verified_capture, record_verified_refund


@skipUnless(connection.vendor == "postgresql", "Financial row locking requires PostgreSQL")
class PaymentConcurrencyTests(TransactionTestCase):
    def setUp(self):
        PaymentCaptureTests.setUp(self)

    @staticmethod
    def capture(attempt_id):
        connections.close_all()
        try:
            return record_verified_capture(attempt_id, VerifiedCapture("race-capture", 25000, "TOMAN"))
        finally:
            connections.close_all()

    @staticmethod
    def refund(args):
        connections.close_all()
        try:
            attempt_id, reference, amount = args
            try:
                return record_verified_refund(attempt_id, reference, amount).pk
            except ValueError:
                return "rejected"
        finally:
            connections.close_all()

    def test_duplicate_capture_commits_stock_once(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.capture, [self.attempt.pk] * 2))
        self.assertEqual(results, [True, True])
        self.offer.refresh_from_db()
        self.assertEqual((self.offer.available_quantity, self.offer.reserved_quantity), (3, 0))
        self.assertEqual(LedgerEntry.objects.filter(kind="payment_capture").count(), 1)

    def test_concurrent_refunds_cannot_exceed_capture(self):
        self.capture(self.attempt.pk)
        inputs = [(self.attempt.pk, "refund-one", 15000), (self.attempt.pk, "refund-two", 15000)]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.refund, inputs))
        self.assertEqual(sum(isinstance(result, int) for result in results), 1)
        self.assertIn("rejected", results)
        self.assertEqual(LedgerEntry.objects.filter(kind="payment_refund").count(), 1)
