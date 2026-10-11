import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, RequestFactory
from .models import SupportTicket, TicketMessage
from .support_api import tickets


class SupportHistoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('09123456921')
        self.other = get_user_model().objects.create_user('09123456922')
        self.staff = get_user_model().objects.create_user('09123456923', is_staff=True)
        self.staff.groups.add(Group.objects.create(name='support_agent'))
        self.ticket = SupportTicket.objects.create(user=self.user, subject='Long history')
        for i in range(45):
            TicketMessage.objects.create(ticket=self.ticket, author=self.user, body=f'Public {i}')
            TicketMessage.objects.create(ticket=self.ticket, author=self.staff, body=f'Private {i}', is_internal=True)
        self.client.force_login(self.user)
        self.base = '/api/v1/operations/my-tickets/'

    def test_customer_cursor_traverses_all_public_messages_once(self):
        path = f'{self.base}{self.ticket.pk}/'
        ids = []
        while True:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            row = response.json()['ticket']
            self.assertLessEqual(len(row['messages']), 20)
            self.assertTrue(all(not message['is_internal'] for message in row['messages']))
            ids = [message['id'] for message in row['messages']] + ids
            if not row['has_older_messages']:
                break
            path = f'{self.base}{self.ticket.pk}/?before={row["before_message"]}'
        self.assertEqual(ids, list(self.ticket.messages.filter(is_internal=False).values_list('pk', flat=True)))
        self.assertEqual(len(set(ids)), 45)

    def test_history_is_private_and_staff_sees_internal_messages(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'{self.base}{self.ticket.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/v1/operations/tickets/{self.ticket.pk}/').status_code, 403)
        self.client.force_login(self.staff)
        result = self.client.get(f'/api/v1/operations/tickets/{self.ticket.pk}/').json()['ticket']
        self.assertTrue(any(message['is_internal'] for message in result['messages']))
        self.client.logout()
        self.assertEqual(self.client.get(f'{self.base}{self.ticket.pk}/').status_code, 401)

    def test_invalid_cursors_are_rejected(self):
        for query in ['before=0', 'before=-1', 'before=true', 'before=1&before=2', 'before=99999999999999999999', 'after=1', 'before=۱۲']:
            self.assertEqual(self.client.get(f'{self.base}{self.ticket.pk}/?{query}').status_code, 400, query)

    def test_insert_between_history_pages_does_not_shift_cursor(self):
        first = self.client.get(f'{self.base}{self.ticket.pk}/').json()['ticket']
        new = TicketMessage.objects.create(ticket=self.ticket, author=self.user, body='New message')
        older = self.client.get(f'{self.base}{self.ticket.pk}/?before={first["before_message"]}').json()['ticket']
        self.assertTrue(all(message['id'] < first['before_message'] for message in older['messages']))
        self.assertNotIn(new.pk, [message['id'] for message in older['messages']])

    def test_queue_queries_and_response_are_bounded(self):
        for i in range(30):
            row = SupportTicket.objects.create(user=self.user, subject=f'Ticket {i}')
            TicketMessage.objects.bulk_create([TicketMessage(ticket=row, author=self.user, body='Message') for _ in range(25)])
        request = RequestFactory().get(self.base)
        request.user = self.user
        with self.assertNumQueries(2):
            result = json.loads(tickets(request).content)
        self.assertEqual(len(result['tickets']), 25)
        self.assertTrue(result['has_next'])
        self.assertTrue(all(len(row['messages']) == 20 for row in result['tickets']))
        second = self.client.get(f'{self.base}?page=2').json()
        self.assertEqual(len(second['tickets']), 6)
        self.assertFalse(second['has_next'])
        self.assertFalse({r['id'] for r in result['tickets']} & {r['id'] for r in second['tickets']})

    def test_staff_filters_and_customer_filter_restrictions(self):
        SupportTicket.objects.filter(pk=self.ticket.pk).update(assigned_to=self.staff, priority='urgent', is_escalated=True)
        self.assertEqual(self.client.get(f'{self.base}?assigned=mine').status_code, 400)
        self.client.force_login(self.staff)
        base = '/api/v1/operations/tickets/'
        result = self.client.get(f'{base}?assigned=mine&priority=urgent&escalated=true&status=open').json()
        self.assertEqual([row['id'] for row in result['tickets']], [self.ticket.pk])
        self.assertEqual(self.client.get(f'{base}?assigned=unassigned').json()['tickets'], [])
        for query in ['page=0', 'page=10001', 'status=invalid', 'priority=invalid', 'assigned=123', 'escalated=1', 'page=1&page=2']:
            self.assertEqual(self.client.get(f'{base}?{query}').status_code, 400, query)

    def test_empty_history_and_boundary_cursor(self):
        empty = SupportTicket.objects.create(user=self.user, subject='Empty fixture')
        row = self.client.get(f'{self.base}{empty.pk}/').json()['ticket']
        self.assertEqual(row['messages'], [])
        self.assertFalse(row['has_older_messages'])
        self.assertIsNone(row['before_message'])
        self.assertEqual(self.client.get(f'{self.base}{self.ticket.pk}/?before=1').json()['ticket']['messages'], [])
