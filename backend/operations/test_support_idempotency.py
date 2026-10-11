import json
from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from .models import AuditEvent, Notification, SupportTicket, TicketMessage, SupportWriteReceipt


class SupportIdempotencyTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user('09123456911')
        self.other = get_user_model().objects.create_user('09123456912')
        self.staff = get_user_model().objects.create_user('09123456913', is_staff=True)
        self.staff.groups.add(Group.objects.create(name='support_agent'))
        self.client.force_login(self.buyer)
        self.key = str(uuid4())
        self.payload = {'subject': 'Delivery question', 'body': 'Please help', 'request_key': self.key}
        self.base = '/api/v1/operations/my-tickets/'

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type='application/json')

    def create(self):
        return self.post(self.base, self.payload).json()['ticket']['id']

    def test_create_retry_is_single_ticket_and_actor_scoped(self):
        first = self.post(self.base, self.payload)
        retry = self.post(self.base, self.payload)
        self.assertEqual((first.status_code, retry.status_code), (201, 201))
        self.assertTrue(retry.json()['replayed'])
        self.assertEqual(SupportTicket.objects.count(), 1)
        self.assertEqual(TicketMessage.objects.count(), 1)
        self.client.force_login(self.other)
        self.assertEqual(self.post(self.base, self.payload).status_code, 201)
        self.assertEqual(SupportWriteReceipt.objects.count(), 2)

    def test_key_cannot_be_reused_with_changed_body_or_endpoint(self):
        ticket_id = self.create()
        changed = {**self.payload, 'body': 'Changed'}
        self.assertEqual(self.post(self.base, changed).status_code, 409)
        self.assertEqual(self.post(f'{self.base}{ticket_id}/reply/', {'body': 'Please help', 'request_key': self.key}).status_code, 409)
        self.assertEqual(TicketMessage.objects.count(), 1)

    def test_customer_retry_after_close_does_not_reopen_or_leak_notes(self):
        ticket_id = self.create()
        path = f'{self.base}{ticket_id}/reply/'
        payload = {'body': 'Follow up', 'request_key': str(uuid4())}
        self.assertEqual(self.post(path, payload).status_code, 200)
        SupportTicket.objects.filter(pk=ticket_id).update(status='closed')
        TicketMessage.objects.create(ticket_id=ticket_id, author=self.staff, body='Secret', is_internal=True)
        result = self.post(path, payload)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['ticket']['status'], 'closed')
        self.assertEqual(len(result.json()['ticket']['messages']), 2)
        self.assertNotIn('Secret', result.content.decode())
        self.client.force_login(self.other)
        self.assertEqual(self.post(path, payload).status_code, 404)

    def test_staff_retry_emits_one_audit_and_one_notification(self):
        ticket_id = self.create()
        self.client.force_login(self.staff)
        path = f'/api/v1/operations/tickets/{ticket_id}/reply/'
        payload = {'body': 'Response', 'status': 'awaiting_customer', 'reason': 'Customer update', 'request_key': str(uuid4())}
        self.assertEqual(self.post(path, payload).status_code, 200)
        self.assertEqual(self.post(path, payload).status_code, 200)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action='support_reply').count(), 1)
        self.staff.groups.clear()
        self.assertEqual(self.post(path, payload).status_code, 403)

    def test_route_retry_preserves_newer_state(self):
        ticket_id = self.create()
        self.client.force_login(self.staff)
        path = f'/api/v1/operations/tickets/{ticket_id}/route/'
        payload = {'assigned_to': self.staff.pk, 'priority': 'high', 'is_escalated': False, 'reason': 'Assign support', 'request_key': str(uuid4())}
        self.assertEqual(self.post(path, payload).status_code, 200)
        SupportTicket.objects.filter(pk=ticket_id).update(priority='urgent')
        self.assertEqual(self.post(path, payload).json()['ticket']['priority'], 'urgent')
        self.assertEqual(AuditEvent.objects.filter(action='support_routed').count(), 1)

    def test_failed_write_does_not_consume_key(self):
        ticket_id = self.create()
        self.client.force_login(self.staff)
        payload = {'body': 'Response', 'status': 'open', 'reason': 'Customer update', 'request_key': str(uuid4())}
        path = f'/api/v1/operations/tickets/{ticket_id}/reply/'
        with patch('operations.support_api._audit', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                self.post(path, payload)
        self.assertEqual(TicketMessage.objects.count(), 1)
        self.assertFalse(SupportWriteReceipt.objects.filter(request_key=payload['request_key']).exists())
        self.assertEqual(self.post(path, payload).status_code, 200)

    def test_invalid_keys_and_zero_order_rejected(self):
        for value in ['', 'invalid', 4, True, None]:
            self.assertEqual(self.post(self.base, {**self.payload, 'request_key': value}).status_code, 400)
        self.assertEqual(self.post(self.base, {**self.payload, 'order_id': 0}).status_code, 400)
        self.assertFalse(SupportTicket.objects.exists())

    def test_key_order_does_not_change_digest_and_legacy_still_works(self):
        self.create()
        self.assertTrue(self.post(self.base, dict(reversed(list(self.payload.items())))).json()['replayed'])
        legacy = {'subject': 'Legacy request', 'body': 'No key'}
        self.assertEqual(self.post(self.base, legacy).status_code, 201)
        self.assertEqual(self.post(self.base, legacy).status_code, 201)
        self.assertEqual(SupportWriteReceipt.objects.count(), 1)
