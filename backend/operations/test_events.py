import json
from datetime import timedelta
from unittest.mock import patch
from django.db import transaction
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from payments.tests import PaymentCaptureTests
from payments.services import record_verified_capture, VerifiedCapture
from .events import emit, process_event, drain, MAX_ATTEMPTS
from .models import OutboxEvent, Notification, AuditEvent


class OutboxTests(TestCase):
    def setUp(self):
        PaymentCaptureTests.setUp(self)

    def event(self):
        with transaction.atomic():
            return emit("test-event", "order.created", order_id=self.order.pk)

    def test_domain_event_and_notification_are_idempotent(self):
        capture = VerifiedCapture("verified-outbox", self.order.grand_total_toman, "TOMAN")
        record_verified_capture(self.attempt.pk, capture)
        record_verified_capture(self.attempt.pk, capture)
        self.assertEqual(OutboxEvent.objects.count(), 1)
        self.assertEqual(drain(), 1)
        self.assertEqual(drain(), 0)
        notification = Notification.objects.get()
        self.assertEqual(notification.user_id, self.order.user_id)
        self.assertEqual(notification.link, "/orders/")

    def test_rollback_discards_domain_event(self):
        try:
            with transaction.atomic():
                emit("rolled-back", "order.created", order_id=self.order.pk)
                raise ValueError("domain failed")
        except ValueError:
            pass
        self.assertFalse(OutboxEvent.objects.exists())

    def test_partial_handler_failure_rolls_back_and_dead_letters(self):
        event = self.event()
        def broken(row):
            Notification.objects.create(user=self.order.user, title="partial", body="partial", event_key="partial")
            raise RuntimeError("secret must not be recorded")
        now = timezone.now()
        with patch("operations.events.handle", side_effect=broken):
            for _ in range(MAX_ATTEMPTS):
                self.assertFalse(process_event(event.pk, now))
                now += timedelta(hours=2)
        event.refresh_from_db()
        self.assertEqual(event.status, "dead")
        self.assertEqual(event.last_error, "RuntimeError")
        self.assertFalse(Notification.objects.exists())
        self.assertFalse(process_event(event.pk, now))

    def test_replay_requires_admin_and_reason_and_reuses_dedup_key(self):
        event = self.event()
        OutboxEvent.objects.filter(pk=event.pk).update(status="dead")
        path = f"/api/v1/operations/events/{event.pk}/replay/"
        self.client.force_login(self.order.user)
        self.assertEqual(self.client.post(path, json.dumps({"reason": "Retry after fix"}), content_type="application/json").status_code, 403)
        admin = get_user_model().objects.create_superuser("09123456999", "local-test-password")
        self.client.force_login(admin)
        self.assertEqual(self.client.post(path, json.dumps({"reason": "Retry after fix"}), content_type="application/json").status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(action="outbox_replayed").exists())
        self.assertTrue(process_event(event.pk))
        self.assertFalse(process_event(event.pk))
        self.assertEqual(Notification.objects.count(), 1)

    def test_existing_event_key_cannot_change_payload(self):
        self.event()
        with self.assertRaises(ValueError), transaction.atomic():
            emit("test-event", "order.cancelled", order_id=self.order.pk)
