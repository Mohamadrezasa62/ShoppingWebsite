import json
from uuid import uuid4
from unittest.mock import patch
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, RequestFactory, Client, override_settings
from django.utils import timezone
from django.core.cache import cache
from operations.models import AuditEvent
from . import tests as fixtures
from . import zarinpal
from .models import PaymentAttempt, LedgerEntry
from .reconciliation_api import order_attempts


@override_settings(ZARINPAL_ENABLED=True, ZARINPAL_MERCHANT_ID='12345678-1234-1234-1234-123456789012', SITE_URL='https://shop.test')
class ReconciliationTests(TestCase):
    def setUp(self):
        fixtures.PaymentCaptureTests.setUp(self)
        self.attempt.delete()
        self.user = self.order.user
        self.other = get_user_model().objects.create_user('09123456951')
        self.finance = get_user_model().objects.create_user('09123456952', is_staff=True)
        self.finance.groups.add(Group.objects.create(name='finance_operator'))
        cache.clear()
        with patch('payments.zarinpal.post', return_value={'code': 100, 'authority': 'A'+'1'*35}):
            self.attempt = zarinpal.initiate(self.user, self.order.pk, str(uuid4()))
        self.owner_path = f'/api/v1/payments/orders/{self.order.pk}/attempts/'
        self.queue_path = '/api/v1/payments/finance/queue/'
        self.verify_path = f'/api/v1/payments/finance/{self.attempt.pk}/verify/'

    def post(self, data):
        return self.client.post(self.verify_path, json.dumps(data), content_type='application/json')

    def test_customer_history_is_owned_and_hides_tokens_and_credentials(self):
        self.client.force_login(self.user)
        result = self.client.get(self.owner_path)
        row = result.json()['payments'][0]
        self.assertTrue(row['can_verify'])
        self.assertTrue(row['checkout_url'].startswith('https://payment.zarinpal.com/'))
        self.assertNotIn(self.attempt.callback_token, result.content.decode())
        self.assertNotIn(self.attempt.gateway_merchant, result.content.decode())
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.owner_path).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.owner_path).status_code, 401)

    def test_expired_order_hides_resume_but_preserves_verification(self):
        self.order.expires_at = timezone.now() - timedelta(seconds=1)
        self.order.save(update_fields=['expires_at'])
        self.client.force_login(self.user)
        row = self.client.get(self.owner_path).json()['payments'][0]
        self.assertEqual(row['checkout_url'], '')
        self.assertTrue(row['can_verify'])

    def test_finance_queue_role_and_field_restrictions(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.queue_path).status_code, 403)
        self.client.force_login(self.finance)
        result = self.client.get(self.queue_path)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['payments'][0]['checkout_url'], '')
        self.assertNotIn(self.attempt.callback_token, result.content.decode())
        for query in ['before=0', 'before=true', 'before=1&before=2', 'status=wrong', 'provider=wrong', 'amount=1']:
            self.assertEqual(self.client.get(f'{self.queue_path}?{query}').status_code, 400, query)

    def test_cash_totals_are_separate_and_nonduplicated(self):
        with patch('payments.zarinpal.post', return_value={'code': 100, 'ref_id': 900}):
            zarinpal.verify(self.attempt.pk)
        from .services import record_verified_refund
        record_verified_refund(self.attempt.pk, 'refund-1', 1000)
        record_verified_refund(self.attempt.pk, 'refund-2', 2000)
        self.client.force_login(self.user)
        row = self.client.get(self.owner_path).json()['payments'][0]
        self.assertEqual((row['captured_toman'], row['refunded_toman']), (25000, 3000))
        self.assertEqual(row['receipt'], 'zarinpal:900')
        self.assertFalse(row['can_verify'])
        self.assertEqual(row['checkout_url'], '')

    def test_staff_verification_is_audited_and_money_is_idempotent(self):
        self.client.force_login(self.finance)
        with patch('payments.zarinpal.post', return_value={'code': 100, 'ref_id': 900}) as remote:
            self.assertEqual(self.post({'reason': 'Customer callback failed'}).status_code, 200)
            self.assertEqual(self.post({'reason': 'Confirm existing receipt'}).status_code, 200)
        self.assertEqual(remote.call_count, 1)
        self.assertEqual(LedgerEntry.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action='payment_reverified').count(), 2)
        event = AuditEvent.objects.filter(action='payment_reverified').first()
        self.assertNotIn(self.attempt.callback_token, json.dumps(event.after))

    def test_audit_failure_rolls_back_capture_then_101_recovers(self):
        self.client.force_login(self.finance)
        with patch('payments.zarinpal.post', return_value={'code': 100, 'ref_id': 900}), patch('payments.reconciliation_api._audit', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.post({'reason': 'Recover payment'})
        self.assertFalse(LedgerEntry.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action='payment_reverified').exists())
        with patch('payments.zarinpal.post', return_value={'code': 101, 'ref_id': 900}):
            self.assertEqual(self.post({'reason': 'Recover payment'}).status_code, 200)
        self.assertEqual(LedgerEntry.objects.count(), 1)

    def test_unknown_authority_cannot_be_manually_paid_or_discarded(self):
        PaymentAttempt.objects.filter(pk=self.attempt.pk).update(status='initiation_unknown', gateway_authority='')
        self.client.force_login(self.finance)
        with patch('payments.zarinpal.post') as remote:
            self.assertEqual(self.post({'reason': 'Investigate provider records'}).status_code, 409)
            self.assertEqual(self.post({'reason': 'Investigate', 'authority': 'invented', 'paid': True}).status_code, 400)
            remote.assert_not_called()
        self.assertFalse(LedgerEntry.objects.exists())
        row = self.client.get(self.queue_path).json()['payments'][0]
        self.assertTrue(row['needs_provider_reconciliation'])
        self.assertFalse(row['can_verify'])

    def test_history_queries_and_cursor_pages_are_bounded(self):
        PaymentAttempt.objects.bulk_create([PaymentAttempt(order=self.order, provider='sandbox', status='rejected', amount_toman=25000, idempotency_key=uuid4()) for _ in range(30)])
        request = RequestFactory().get(self.owner_path)
        request.user = self.user
        with self.assertNumQueries(2):
            first = json.loads(order_attempts(request, self.order.pk).content)
        self.assertEqual(len(first['payments']), 25)
        self.assertTrue(first['has_next'])
        self.client.force_login(self.user)
        second = self.client.get(f'{self.owner_path}?before={first["next_before"]}').json()
        self.assertEqual(len(second['payments']), 6)
        self.assertFalse(second['has_next'])
        self.assertFalse({r['id'] for r in first['payments']} & {r['id'] for r in second['payments']})

    def test_provider_timeout_keeps_queue_and_financial_state(self):
        self.client.force_login(self.finance)
        with patch('payments.zarinpal.post', side_effect=zarinpal.GatewayUnavailable()):
            self.assertEqual(self.post({'reason': 'Recover callback'}).status_code, 503)
        self.assertFalse(LedgerEntry.objects.exists())
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, 'redirected')

    def test_staff_writes_require_csrf_and_reason(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.finance)
        self.assertEqual(protected.post(self.verify_path, '{"reason":"Recover payment"}', content_type='application/json').status_code, 403)
        self.client.force_login(self.finance)
        for body in [{}, {'reason': 'x'}, {'reason': 'null\x00byte'}, {'reason': 'Investigate', 'amount': 1}]:
            self.assertEqual(self.post(body).status_code, 400)

    def test_inactive_actor_is_rechecked_inside_staff_transaction(self):
        from .reconciliation_api import staff_verify
        request = RequestFactory().post(self.verify_path, '{"reason":"Recover payment"}', content_type='application/json')
        request.user = self.finance
        request._dont_enforce_csrf_checks = True
        get_user_model().objects.filter(pk=self.finance.pk).update(is_active=False)
        with patch('payments.zarinpal.post') as remote:
            self.assertEqual(staff_verify(request, self.attempt.pk).status_code, 403)
            remote.assert_not_called()
        self.assertFalse(LedgerEntry.objects.exists())

    def export(self, query='', data=None):
        return self.client.post('/api/v1/payments/finance/queue/export/' + query,
                                json.dumps(data if data is not None else {'reason': 'Reconcile provider records'}),
                                content_type='application/json')

    def csv_rows(self, response):
        import csv
        from io import StringIO
        return list(csv.DictReader(StringIO(response.content.decode('utf-8-sig'))))

    def test_export_role_csrf_and_validation(self):
        self.assertEqual(self.export().status_code, 401)
        self.client.force_login(self.user)
        self.assertEqual(self.export().status_code, 403)
        self.client.force_login(self.finance)
        for query in ['?status=wrong', '?provider=wrong', '?before=0', '?before=1&before=2', '?amount=1']:
            self.assertEqual(self.export(query).status_code, 400)
        for data in [{}, {'reason': 'x'}, {'reason': 'bad\x00reason'}, {'reason': 'Review records', 'paid': True}]:
            self.assertEqual(self.export(data=data).status_code, 400)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.finance)
        self.assertEqual(protected.post('/api/v1/payments/finance/queue/export/', '{"reason":"Reconcile records"}', content_type='application/json').status_code, 403)
        self.assertFalse(AuditEvent.objects.filter(action='payment_queue_exported').exists())

    def test_export_private_fields_units_and_audit(self):
        self.client.force_login(self.finance)
        with patch('payments.zarinpal.post') as remote:
            response = self.export()
            remote.assert_not_called()
        self.assertEqual(response.status_code, 200)
        row = self.csv_rows(response)[0]
        self.assertEqual(row['gateway_authority'], self.attempt.gateway_authority)
        self.assertEqual((row['expected_toman'], row['expected_irr']), ('25000', '250000'))
        self.assertEqual((row['captured_toman'], row['refunded_toman']), ('0', '0'))
        for secret in [self.attempt.callback_token, self.attempt.gateway_merchant, self.user.phone, self.attempt.checkout_url]:
            self.assertNotIn(secret, response.content.decode())
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Has-Next'], 'false')
        audit = AuditEvent.objects.get(action='payment_queue_exported')
        self.assertEqual(audit.after['attempt_ids'], [self.attempt.pk])
        self.assertNotIn(self.attempt.gateway_authority, json.dumps(audit.after))
        self.assertFalse(LedgerEntry.objects.exists())
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, 'redirected')

    def test_export_page_filters_cursor_and_formula_protection(self):
        PaymentAttempt.objects.bulk_create([PaymentAttempt(order=self.order, provider='sandbox', status='rejected', amount_toman=10, idempotency_key=uuid4()) for _ in range(30)])
        PaymentAttempt.objects.filter(pk=self.attempt.pk).update(provider_reference=' \t=HYPERLINK("evil")', gateway_authority='+formula')
        self.client.force_login(self.finance)
        first = self.export('?status=rejected&provider=sandbox')
        self.assertEqual(len(self.csv_rows(first)), 25)
        self.assertEqual(first['X-Has-Next'], 'true')
        second = self.export('?status=rejected&provider=sandbox&before=' + first['X-Next-Before'])
        self.assertEqual(len(self.csv_rows(second)), 5)
        self.assertEqual(second['X-Has-Next'], 'false')
        self.assertFalse({r['attempt_id'] for r in self.csv_rows(first)} & {r['attempt_id'] for r in self.csv_rows(second)})
        row = self.csv_rows(self.export())[0]
        self.assertTrue(row['provider_reference'].startswith("'"))
        self.assertEqual(row['gateway_authority'], "'+formula")

    def test_export_cash_refunds_and_unknown_are_not_payment_approval(self):
        with patch('payments.zarinpal.post', return_value={'code': 100, 'ref_id': 900}):
            zarinpal.verify(self.attempt.pk)
        from .services import record_verified_refund
        record_verified_refund(self.attempt.pk, 'refund-export-1', 1000)
        record_verified_refund(self.attempt.pk, 'refund-export-2', 2000)
        self.client.force_login(self.finance)
        row = self.csv_rows(self.export('?status=captured'))[0]
        self.assertEqual((row['captured_toman'], row['refunded_toman']), ('25000', '3000'))
        PaymentAttempt.objects.filter(pk=self.attempt.pk).update(status='initiation_unknown', gateway_authority='')
        row = self.csv_rows(self.export())[0]
        self.assertEqual(row['needs_provider_reconciliation'], 'True')
        self.assertEqual(row['gateway_authority'], '')

    def test_export_audit_failure_returns_no_file(self):
        self.client.force_login(self.finance)
        with patch('payments.reconciliation_api._audit', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.export()
        self.assertFalse(AuditEvent.objects.filter(action='payment_queue_exported').exists())
        self.assertFalse(LedgerEntry.objects.exists())

    def test_export_rechecks_active_actor(self):
        from .reconciliation_api import export_queue
        request = RequestFactory().post('/api/v1/payments/finance/queue/export/', '{"reason":"Reconcile records"}', content_type='application/json')
        request.user = self.finance
        request._dont_enforce_csrf_checks = True
        get_user_model().objects.filter(pk=self.finance.pk).update(is_active=False)
        self.assertEqual(export_queue(request).status_code, 403)
        self.assertFalse(AuditEvent.objects.filter(action='payment_queue_exported').exists())
