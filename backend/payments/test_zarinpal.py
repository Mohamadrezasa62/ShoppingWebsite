import json
from uuid import uuid4
from unittest.mock import patch, MagicMock
from django.test import TestCase, SimpleTestCase, override_settings
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from . import tests as fixtures
from .models import PaymentAttempt, LedgerEntry
from . import zarinpal
from .orchestration import PaymentError


@override_settings(ZARINPAL_ENABLED=True, ZARINPAL_MERCHANT_ID='12345678-1234-1234-1234-123456789012', SITE_URL='https://shop.test')
class ZarinpalTests(TestCase):
    def setUp(self):
        fixtures.PaymentCaptureTests.setUp(self)
        self.attempt.delete()
        self.user = self.order.user
        self.key = str(uuid4())
        self.authority = 'A' + '1' * 35
        cache.clear()

    def start(self):
        with patch('payments.zarinpal.post', return_value={'code': 100, 'authority': self.authority}):
            return zarinpal.initiate(self.user, self.order.pk, self.key)

    def test_creation_is_idempotent_and_amount_is_server_snapshot_in_rials(self):
        with patch('payments.zarinpal.post', return_value={'code': 100, 'authority': self.authority}) as remote:
            first = zarinpal.initiate(self.user, self.order.pk, self.key)
            second = zarinpal.initiate(self.user, self.order.pk, self.key)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(remote.call_count, 1)
        payload = remote.call_args.args[1]
        self.assertEqual(payload['amount'], 250000)
        self.assertEqual(payload['currency'], 'IRR')
        self.assertIn(first.callback_token, payload['callback_url'])
        self.assertEqual(len(first.callback_token), 64)
        self.assertEqual(first.provider_reference, '')
        self.assertFalse(LedgerEntry.objects.exists())

    def test_uncertain_initiation_never_retries_even_with_new_key(self):
        with patch('payments.zarinpal.post', side_effect=zarinpal.GatewayUnavailable()) as remote:
            for key in [self.key, self.key, str(uuid4())]:
                with self.assertRaises(PaymentError):
                    zarinpal.initiate(self.user, self.order.pk, key)
        self.assertEqual(remote.call_count, 1)
        self.assertEqual(PaymentAttempt.objects.get().status, 'initiation_unknown')
        self.assertFalse(LedgerEntry.objects.exists())

    def test_verified_capture_and_duplicate_verify_commit_stock_once(self):
        attempt = self.start()
        with patch('payments.zarinpal.post', return_value={'code': 100, 'ref_id': 789}) as remote:
            first = zarinpal.verify(attempt.pk)
            second = zarinpal.verify(attempt.pk)
        self.assertEqual(first.status, 'captured')
        self.assertEqual(second.provider_reference, 'zarinpal:789')
        self.assertEqual(remote.call_count, 1)
        self.assertEqual(remote.call_args.args[1]['amount'], 250000)
        self.offer.refresh_from_db()
        self.assertEqual((self.offer.available_quantity, self.offer.reserved_quantity), (3, 0))
        self.assertEqual(LedgerEntry.objects.count(), 1)

    def test_101_recovers_after_database_rollback(self):
        attempt = self.start()
        from .services import record_verified_capture
        def failure(*args):
            record_verified_capture(*args)
            raise RuntimeError('transaction interrupted')
        with patch('payments.zarinpal.post', return_value={'code': 100, 'ref_id': 789}), patch('payments.zarinpal.record_verified_capture', side_effect=failure):
            with self.assertRaises(RuntimeError):
                zarinpal.verify(attempt.pk)
        self.assertFalse(LedgerEntry.objects.exists())
        with patch('payments.zarinpal.post', return_value={'code': 101, 'ref_id': 789}):
            self.assertEqual(zarinpal.verify(attempt.pk).status, 'captured')
        self.assertEqual(LedgerEntry.objects.count(), 1)

    def test_late_money_is_recorded_for_review_without_fulfillment(self):
        attempt = self.start()
        self.order.expires_at = timezone.now() - timedelta(seconds=1)
        self.order.save(update_fields=['expires_at'])
        with patch('payments.zarinpal.post', return_value={'code': 100, 'ref_id': 789}):
            self.assertEqual(zarinpal.verify(attempt.pk).status, 'review_required')
        self.order.refresh_from_db()
        self.offer.refresh_from_db()
        self.assertEqual(self.order.status, 'pending_payment')
        self.assertEqual(self.offer.reserved_quantity, 2)
        self.assertEqual(LedgerEntry.objects.get().amount_toman, 25000)

    def test_forged_or_cancelled_callback_never_marks_paid(self):
        attempt = self.start()
        base = f'/api/v1/payments/zarinpal/callback/{attempt.callback_token}/'
        with patch('payments.zarinpal.post') as remote:
            self.assertEqual(self.client.get(base, {'Authority': 'forged', 'Status': 'OK'}).status_code, 400)
            self.assertEqual(self.client.get(base, {'Authority': self.authority, 'Status': 'NOK'}).status_code, 302)
            self.assertEqual(self.client.get(base + '?Authority=x&Authority=y&Status=OK').status_code, 400)
            remote.assert_not_called()
        self.assertFalse(LedgerEntry.objects.exists())

    def test_callback_verifies_server_side_and_hides_private_data(self):
        attempt = self.start()
        with patch('payments.zarinpal.post', return_value={'code': 100, 'ref_id': 789}):
            response = self.client.get(f'/api/v1/payments/zarinpal/callback/{attempt.callback_token}/', {'Authority': self.authority, 'Status': 'OK'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/orders/')
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertEqual(LedgerEntry.objects.count(), 1)

    def test_owner_retry_is_private_and_timeout_never_records_money(self):
        attempt = self.start()
        path = f'/api/v1/payments/{attempt.pk}/verify/'
        self.assertEqual(self.client.post(path, '{}', content_type='application/json').status_code, 401)
        self.client.force_login(self.user)
        with patch('payments.zarinpal.post', side_effect=zarinpal.GatewayUnavailable()):
            self.assertEqual(self.client.post(path, '{}', content_type='application/json').status_code, 503)
        self.assertFalse(LedgerEntry.objects.exists())
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'redirected')

    def test_disabling_new_payments_does_not_prevent_known_verification(self):
        attempt = self.start()
        with override_settings(ZARINPAL_MERCHANT_ID=''), patch('payments.zarinpal.post') as unavailable:
            with self.assertRaises(PaymentError) as mismatch:
                zarinpal.verify(attempt.pk)
            self.assertEqual(mismatch.exception.code, 'verification_credentials_changed')
            unavailable.assert_not_called()
        with override_settings(ZARINPAL_ENABLED=False), patch('payments.zarinpal.post', return_value={'code': 101, 'ref_id': 789}) as remote:
            self.assertEqual(zarinpal.verify(attempt.pk).status, 'captured')
            self.assertEqual(remote.call_args.args[1]['merchant_id'], '12345678-1234-1234-1234-123456789012')
            self.assertNotEqual(attempt.gateway_merchant, remote.call_args.args[1]['merchant_id'])
            with self.assertRaises(PaymentError):
                zarinpal.initiate(self.user, self.order.pk, str(uuid4()))

    def test_negative_verify_and_invalid_receipt_cannot_capture(self):
        attempt = self.start()
        for payload in [{'code': -21}, {'code': 100, 'ref_id': True}, {'code': 101, 'ref_id': 0}]:
            with patch('payments.zarinpal.post', return_value=payload):
                with self.assertRaises(PaymentError):
                    zarinpal.verify(attempt.pk)
        self.assertFalse(LedgerEntry.objects.exists())

    def test_same_provider_receipt_cannot_capture_a_second_attempt(self):
        first = self.start()
        with patch('payments.zarinpal.post', return_value={'code': 100, 'ref_id': 789}):
            zarinpal.verify(first.pk)
        second = PaymentAttempt.objects.create(order=self.order, provider='zarinpal', status='redirected', amount_toman=25000, idempotency_key=uuid4(), gateway_authority='A'+'2'*35, gateway_merchant=first.gateway_merchant)
        with patch('payments.zarinpal.post', return_value={'code': 101, 'ref_id': 789}):
            with self.assertRaises(PaymentError) as error:
                zarinpal.verify(second.pk)
        self.assertEqual(error.exception.code, 'verification_conflict')
        self.assertEqual(LedgerEntry.objects.count(), 1)
        second.refresh_from_db()
        self.assertEqual(second.status, 'redirected')


class ZarinpalTransportTests(SimpleTestCase):
    def test_fixed_https_post_redacts_failures_and_rejects_large_response(self):
        opener = MagicMock()
        opener.open.side_effect = TimeoutError('secret merchant and card')
        with patch('payments.zarinpal.build_opener', return_value=opener):
            with self.assertRaises(zarinpal.GatewayUnavailable) as result:
                zarinpal.post('verify', {'amount': 1000})
        self.assertEqual(str(result.exception), '')
        self.assertEqual(opener.open.call_count, 1)
        self.assertTrue(opener.open.call_args.args[0].full_url.startswith('https://payment.zarinpal.com/'))
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 10)
        opener.open.side_effect = None
        response = opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'x' * 65537
        with patch('payments.zarinpal.build_opener', return_value=opener):
            with self.assertRaises(zarinpal.GatewayUnavailable):
                zarinpal.post('verify', {})

    def test_validated_json_and_provider_rejection(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status = 200
        for payload, expected in [({'data': {'code': 100, 'ref_id': 12}}, 100), ({'errors': {'code': -10}}, -10)]:
            response.read.return_value = json.dumps(payload).encode()
            with patch('payments.zarinpal.build_opener', return_value=opener):
                self.assertEqual(zarinpal.post('verify', {})['code'], expected)
        response.read.return_value = b'{"data":{"code":true}}'
        with patch('payments.zarinpal.build_opener', return_value=opener):
            with self.assertRaises(zarinpal.GatewayUnavailable):
                zarinpal.post('verify', {})
