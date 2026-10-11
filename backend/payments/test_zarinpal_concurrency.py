from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from . import tests as fixtures
from .models import LedgerEntry, PaymentAttempt
from .orchestration import PaymentError
from . import zarinpal


@skipUnless(connection.vendor == 'postgresql', 'Gateway serialization requires PostgreSQL')
@override_settings(ZARINPAL_ENABLED=True, ZARINPAL_MERCHANT_ID='12345678-1234-1234-1234-123456789012', SITE_URL='https://shop.test')
class ZarinpalConcurrencyTests(TransactionTestCase):
    def setUp(self):
        fixtures.PaymentCaptureTests.setUp(self)
        self.attempt.delete()
        self.key = str(uuid4())

    def race(self, action):
        gate = Barrier(2)
        def run(_):
            connections.close_all()
            try:
                gate.wait(timeout=10)
                return action()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, range(2)))

    def test_parallel_initiation_does_not_duplicate_provider_requests(self):
        def start():
            try:
                return zarinpal.initiate(self.order.user, self.order.pk, self.key).pk
            except PaymentError as error:
                return error.code
        with patch('payments.zarinpal.post', return_value={'code': 100, 'authority': 'A'+'1'*35}) as remote:
            results = self.race(start)
        self.assertEqual(PaymentAttempt.objects.count(), 1)
        self.assertEqual(remote.call_count, 1)
        self.assertTrue(any(type(result) is int for result in results))
        self.assertTrue(all(type(result) is int or result == 'payment_initiation_unresolved' for result in results))

    def test_parallel_verification_captures_and_consumes_once(self):
        with patch('payments.zarinpal.post', return_value={'code': 100, 'authority': 'A'+'1'*35}):
            attempt = zarinpal.initiate(self.order.user, self.order.pk, self.key)
        with patch('payments.zarinpal.post', return_value={'code': 100, 'ref_id': 456}) as remote:
            self.assertEqual(self.race(lambda: zarinpal.verify(attempt.pk).status), ['captured', 'captured'])
        self.assertEqual(remote.call_count, 1)
        self.assertEqual(LedgerEntry.objects.count(), 1)
        self.offer.refresh_from_db()
        self.assertEqual((self.offer.available_quantity, self.offer.reserved_quantity), (3, 0))

    def test_customer_and_finance_verification_share_one_capture(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        from django.test import RequestFactory
        from operations.models import AuditEvent
        from .reconciliation_api import staff_verify
        actor = get_user_model().objects.create_user('09123456953', is_staff=True)
        actor.groups.add(Group.objects.create(name='finance_operator'))
        with patch('payments.zarinpal.post', return_value={'code': 100, 'authority': 'A'+'1'*35}):
            attempt = zarinpal.initiate(self.order.user, self.order.pk, self.key)
        gate = Barrier(2)
        def run(kind):
            connections.close_all()
            try:
                gate.wait(timeout=10)
                if kind == 'customer':
                    return zarinpal.verify(attempt.pk).status
                request = RequestFactory().post(f'/api/v1/payments/finance/{attempt.pk}/verify/', '{"reason":"Recover callback"}', content_type='application/json')
                request.user = get_user_model().objects.get(pk=actor.pk)
                request._dont_enforce_csrf_checks = True
                return staff_verify(request, attempt.pk).status_code
            finally:
                connections.close_all()
        with patch('payments.zarinpal.post', return_value={'code': 100, 'ref_id': 456}) as remote:
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(list(pool.map(run, ['customer', 'finance'])), ['captured', 200])
        self.assertEqual(remote.call_count, 1)
        self.assertEqual(LedgerEntry.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action='payment_reverified').count(), 1)

    def test_parallel_investigation_retries_append_once(self):
        import json
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        from django.test import RequestFactory
        from operations.models import AuditEvent
        from .investigation_api import append
        from .models import PaymentInvestigationNote
        actor = get_user_model().objects.create_user('09123456955', is_staff=True)
        actor.groups.add(Group.objects.create(name='finance_operator'))
        attempt = PaymentAttempt.objects.create(order=self.order, provider='zarinpal', status='initiation_unknown', amount_toman=25000, idempotency_key=uuid4())
        body = json.dumps({'reason': 'Provider investigation pending', 'request_key': str(uuid4())})
        def write():
            request = RequestFactory().post(f'/api/v1/payments/finance/{attempt.pk}/notes/append/', body, content_type='application/json')
            request.user = get_user_model().objects.get(pk=actor.pk)
            request._dont_enforce_csrf_checks = True
            return append(request, attempt.pk).status_code
        self.assertEqual(sorted(self.race(write)), [200, 201])
        self.assertEqual(PaymentInvestigationNote.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action='payment_investigation_noted').count(), 1)
        self.assertFalse(LedgerEntry.objects.exists())
