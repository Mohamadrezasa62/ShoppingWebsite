from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase
from payments import tests as payment_fixtures
from payments.services import VerifiedCapture, record_verified_capture
from commerce.models import ReturnCase
from commerce.returns import create_line_return
from commerce.services import CheckoutError
from .closure import ClosureError, decide_closure, request_closure


@skipUnless(connection.vendor == "postgresql", "Account/return serialization requires PostgreSQL")
class ClosureConcurrencyTests(TransactionTestCase):
    def setUp(self):
        payment_fixtures.PaymentCaptureTests.setUp(self)
        record_verified_capture(self.attempt.pk, VerifiedCapture("CLOSURE-RACE", 25000, "TOMAN"))
        self.user = self.order.user
        self.delivery = self.order.deliveries.get()
        self.delivery.status = "delivered"
        self.delivery.save(update_fields=["status"])
        self.line = self.delivery.lines.get()
        self.case = request_closure(self.user, "Close account")
        self.actor = get_user_model().objects.create_user("09123456864", is_staff=True)

    def test_closure_and_new_return_cannot_both_commit(self):
        gate = Barrier(2)
        def action(kind):
            connections.close_all()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                gate.wait(timeout=10)
                try:
                    if kind == "return":
                        return create_line_return(user, self.delivery.pk, self.line.pk, 1, "Damaged product").pk
                    return decide_closure(self.case.pk, "completed", self.actor, "Verified request").status
                except (ClosureError, CheckoutError) as exc:
                    return exc.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            returned, closed = list(executor.map(action, ["return", "closure"]))
        self.user.refresh_from_db()
        if closed == "completed":
            self.assertEqual(returned, "account_unavailable")
            self.assertFalse(self.user.is_active)
            self.assertFalse(ReturnCase.objects.exists())
        else:
            self.assertEqual(closed, "closure_blocked")
            self.assertIsInstance(returned, int)
            self.assertTrue(self.user.is_active)
            self.assertEqual(ReturnCase.objects.count(), 1)
