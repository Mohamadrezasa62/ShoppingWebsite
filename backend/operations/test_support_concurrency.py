import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import RequestFactory, TransactionTestCase
from .support_api import tickets
from .models import SupportTicket, TicketMessage, SupportWriteReceipt


@skipUnless(connection.vendor == 'postgresql', 'Support write serialization requires PostgreSQL')
class SupportConcurrencyTests(TransactionTestCase):
    def test_concurrent_duplicate_creates_only_one_ticket(self):
        user = get_user_model().objects.create_user('09123456914')
        key = str(uuid4())
        gate = Barrier(2)
        def send(_):
            connections.close_all()
            try:
                request = RequestFactory().post('/api/v1/operations/my-tickets/', json.dumps({'subject': 'Concurrent request', 'body': 'Please help', 'request_key': key}), content_type='application/json')
                request.user = get_user_model().objects.get(pk=user.pk)
                request._dont_enforce_csrf_checks = True
                gate.wait(timeout=10)
                response = tickets(request)
                return response.status_code, json.loads(response.content)['ticket']['id']
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, range(2)))
        self.assertEqual([status for status, _ in results], [201, 201])
        self.assertEqual(len({ticket for _, ticket in results}), 1)
        self.assertEqual(SupportTicket.objects.count(), 1)
        self.assertEqual(TicketMessage.objects.count(), 1)
        self.assertEqual(SupportWriteReceipt.objects.count(), 1)
