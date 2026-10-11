from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import json
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from catalog.models import Offer
from commerce.models import Order
from operations.invariants import inspect_commerce
from payments import tests as payment_fixtures
from payments.models import LedgerEntry
from payments.services import VerifiedCapture, record_verified_capture, record_verified_refund


class CommerceVerificationTests(TestCase):
    def setUp(self):
        payment_fixtures.PaymentCaptureTests.setUp(self)

    def test_pending_capture_and_partial_refund_remain_consistent(self):
        self.assertTrue(inspect_commerce()["consistent"])
        record_verified_capture(self.attempt.pk, VerifiedCapture("VERIFY-1", self.order.grand_total_toman, "TOMAN"))
        record_verified_refund(self.attempt.pk, "REFUND-1", 1000)
        report = inspect_commerce()
        self.assertTrue(report["consistent"], report["issues"])
        self.assertEqual(report["cash_totals_toman"], {"captured": self.order.grand_total_toman, "refunded": 1000})

    def test_reservation_corruption_is_reported_without_repair(self):
        Offer.objects.filter(pk=self.offer.pk).update(reserved_quantity=1)
        report = inspect_commerce()
        self.assertIn("reservation_mismatch", [row["code"] for row in report["issues"]])
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.reserved_quantity, 1)

    def test_snapshot_and_missing_capture_corruption_are_detected(self):
        Order.objects.filter(pk=self.order.pk).update(grand_total_toman=123, status="paid")
        codes = {row["code"] for row in inspect_commerce()["issues"]}
        self.assertIn("order_snapshot_total_mismatch", codes)
        self.assertIn("paid_order_without_capture", codes)

    def test_excess_refund_is_detected_without_exposing_customer_fields(self):
        record_verified_capture(self.attempt.pk, VerifiedCapture("VERIFY-1", self.order.grand_total_toman, "TOMAN"))
        LedgerEntry.objects.create(order=self.order, attempt=self.attempt, kind="payment_refund", amount_toman=-self.order.grand_total_toman-1, event_key="CORRUPTED-REFUND")
        report = inspect_commerce()
        self.assertIn("refund_exceeds_capture", [row["code"] for row in report["issues"]])
        text = json.dumps(report)
        for private in ("phone", "address_snapshot", "provider_reference", "password"):
            self.assertNotIn(private, text)

    def test_late_capture_for_review_is_not_a_false_integrity_failure(self):
        from commerce.services import cancel_unpaid_order
        cancel_unpaid_order(self.order.pk, self.order.user)
        record_verified_capture(self.attempt.pk, VerifiedCapture("LATE-1", self.order.grand_total_toman, "TOMAN"))
        report = inspect_commerce()
        self.assertTrue(report["consistent"], report["issues"])
        self.assertEqual(report["counts"]["review_required_payments"], 1)

    def test_command_writes_failure_report_and_refuses_overwrite(self):
        Offer.objects.filter(pk=self.offer.pk).update(reserved_quantity=1)
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            with self.assertRaises(CommandError):
                call_command("verify_commerce", output=str(output), stdout=StringIO())
            self.assertFalse(json.loads(output.read_text())["consistent"])
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            original = output.read_bytes()
            with self.assertRaises(CommandError):
                call_command("verify_commerce", output=str(output))
            self.assertEqual(output.read_bytes(), original)
