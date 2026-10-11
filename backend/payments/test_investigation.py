import json
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, RequestFactory, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from operations.models import AuditEvent
from . import tests as fixtures
from .models import PaymentInvestigationNote, PaymentAttempt, LedgerEntry
from .investigation_api import history, append


class InvestigationTests(TestCase):
    def setUp(self):
        fixtures.PaymentCaptureTests.setUp(self)
        self.actor = get_user_model().objects.create_user('09123456954', is_staff=True)
        self.actor.groups.add(Group.objects.create(name='finance_operator'))
        self.path = f'/api/v1/payments/finance/{self.attempt.pk}/notes/'
        self.key = str(uuid4())

    def post(self, reason='Provider investigation pending', key=None, path=None, extra=None):
        data = {'reason': reason, 'request_key': key or self.key}
        data.update(extra or {})
        return self.client.post((path or self.path) + 'append/', json.dumps(data), content_type='application/json')

    def test_private_roles_and_csrf(self):
        self.assertEqual(self.client.get(self.path).status_code, 401)
        self.assertEqual(self.post().status_code, 401)
        self.client.force_login(self.order.user)
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self.post().status_code, 403)
        self.actor.groups.clear()
        self.actor.groups.add(Group.objects.create(name='support_agent'))
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self.post().status_code, 403)
        self.actor.groups.clear()
        self.actor.groups.add(Group.objects.get(name='finance_operator'))
        client = Client(enforce_csrf_checks=True); client.force_login(self.actor)
        self.assertEqual(client.post(self.path + 'append/', '{}', content_type='application/json').status_code, 403)

    def test_append_retry_audit_and_no_money_changes(self):
        self.client.force_login(self.actor)
        original = (self.attempt.status, self.order.status, self.offer.available_quantity, self.offer.reserved_quantity)
        with patch('payments.zarinpal.post') as remote:
            first = self.post('  Provider investigation pending  ')
            second = self.post()
            remote.assert_not_called()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()['replayed'])
        self.assertEqual(first.json()['note']['id'], second.json()['note']['id'])
        self.assertEqual(PaymentInvestigationNote.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action='payment_investigation_noted').count(), 1)
        self.assertFalse(LedgerEntry.objects.exists())
        self.attempt.refresh_from_db(); self.order.refresh_from_db(); self.offer.refresh_from_db()
        self.assertEqual(original, (self.attempt.status, self.order.status, self.offer.available_quantity, self.offer.reserved_quantity))

    def test_changed_retry_payload_or_attempt_conflicts(self):
        self.client.force_login(self.actor)
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.post('Changed investigation').status_code, 409)
        other = PaymentAttempt.objects.create(order=self.order, provider='sandbox', amount_toman=25000, idempotency_key=uuid4())
        self.assertEqual(self.post(path=f'/api/v1/payments/finance/{other.pk}/notes/').status_code, 409)
        self.assertEqual(PaymentInvestigationNote.objects.count(), 1)

    def test_validation_and_missing_attempt(self):
        self.client.force_login(self.actor)
        for reason in ['x', '\x00bad', 'x'*501, 10]:
            self.assertEqual(self.post(reason).status_code, 400)
        for key in ['true', str(uuid4()).replace('-', ''), '00000000-0000-0000-0000-000000000000', str(uuid4()).upper()]:
            self.assertEqual(self.post(key=key).status_code, 400)
        self.assertEqual(self.post(extra={'paid': True}).status_code, 400)
        self.assertEqual(self.client.post(self.path+'append/', '[]', content_type='application/json').status_code, 400)
        self.assertEqual(self.post(path='/api/v1/payments/finance/999999/notes/').status_code, 404)
        for query in ['?before=0', '?before=1&before=2', '?paid=true']:
            self.assertEqual(self.client.get(self.path+query).status_code, 400)
        self.assertFalse(PaymentInvestigationNote.objects.exists())

    def test_audit_failure_rolls_back_key_and_note(self):
        self.client.force_login(self.actor)
        with patch('payments.investigation_api._audit', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.post()
        self.assertFalse(PaymentInvestigationNote.objects.exists())
        self.assertEqual(self.post().status_code, 201)

    def test_history_bounded_and_no_automatic_secret_fields(self):
        PaymentInvestigationNote.objects.bulk_create([PaymentInvestigationNote(attempt=self.attempt, actor=self.actor, request_key=uuid4(), body=f'Investigation {i}') for i in range(25)])
        other = PaymentAttempt.objects.create(order=self.order, provider='sandbox', amount_toman=25000, idempotency_key=uuid4())
        PaymentInvestigationNote.objects.create(attempt=other, actor=self.actor, request_key=uuid4(), body='Other attempt private note')
        request = RequestFactory().get(self.path); request.user = self.actor
        with self.assertNumQueries(3):
            first = json.loads(history(request, self.attempt.pk).content)
        self.assertEqual(len(first['notes']), 20)
        self.client.force_login(self.actor)
        second = self.client.get(self.path + f'?before={first["next_before"]}').json()
        self.assertEqual(len(second['notes']), 5)
        self.assertFalse(second['has_next'])
        self.assertFalse({r['id'] for r in first['notes']} & {r['id'] for r in second['notes']})
        self.assertEqual(set(first['notes'][0]), {'id', 'attempt_id', 'actor_id', 'body', 'created_at'})
        self.assertNotIn('Other attempt', json.dumps(first))
        self.assertEqual(self.client.get(f'/api/v1/payments/orders/{self.order.pk}/attempts/').status_code, 404)

    def test_inactive_actor_cannot_write_or_replay(self):
        self.client.force_login(self.actor)
        self.post()
        request = RequestFactory().post(self.path+'append/', json.dumps({'reason':'Provider investigation pending', 'request_key':self.key}), content_type='application/json')
        request.user = self.actor; request._dont_enforce_csrf_checks = True
        get_user_model().objects.filter(pk=self.actor.pk).update(is_active=False)
        self.assertEqual(append(request, self.attempt.pk).status_code, 403)
        self.assertEqual(PaymentInvestigationNote.objects.count(), 1)

    def test_model_notes_are_append_only(self):
        note = PaymentInvestigationNote.objects.create(attempt=self.attempt, actor=self.actor, request_key=uuid4(), body='Investigation')
        note.body = 'Changed'
        with self.assertRaises(ValueError):
            note.save()

    def test_retry_key_is_actor_scoped_and_customer_history_hides_notes(self):
        self.client.force_login(self.actor)
        self.assertEqual(self.post().status_code, 201)
        other = get_user_model().objects.create_user('09123456956', is_staff=True)
        other.groups.add(Group.objects.get(name='finance_operator'))
        self.client.force_login(other)
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(PaymentInvestigationNote.objects.count(), 2)
        self.client.force_login(self.order.user)
        result = self.client.get(f'/api/v1/payments/orders/{self.order.pk}/attempts/')
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('Provider investigation pending', result.content.decode())
        self.assertNotIn('notes', result.json()['payments'][0])
        self.assertEqual(self.client.get(self.path).status_code, 403)

    def test_role_revocation_denies_replay_and_history(self):
        self.client.force_login(self.actor)
        self.assertEqual(self.post().status_code, 201)
        self.actor.groups.clear()
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(PaymentInvestigationNote.objects.count(), 1)
