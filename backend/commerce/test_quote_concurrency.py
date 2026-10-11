import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection, connections
from django.test import RequestFactory, TransactionTestCase
from operations.configuration_api import shipping_rule
from . import test_quotes as fixtures
from .models import Order
from .services import create_order, CheckoutError


@skipUnless(connection.vendor == "postgresql", "Signed quote and shipping audit locks require PostgreSQL")
class QuoteConcurrencyTests(TransactionTestCase):
    setUp = fixtures.QuoteApprovalTests.setUp
    preview = fixtures.QuoteApprovalTests.preview

    def test_staff_buyer_shipping_edit_and_checkout_do_not_deadlock_or_change_approved_amount(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.user.groups.add(Group.objects.create(name="marketplace_manager"))
        approved = self.preview()
        gate = Barrier(2)
        def purchase():
            user = get_user_model().objects.get(pk=self.user.pk)
            try:
                return create_order(user, self.address.pk, uuid4(), approved["approval_token"])[0].pk
            except CheckoutError as error:
                return error.code
        def edit():
            request = RequestFactory().patch("/shipping-test/", json.dumps({"fee_toman": 1800, "reason": "Reviewed rate change"}), content_type="application/json")
            request.user = get_user_model().objects.get(pk=self.user.pk)
            request._dont_enforce_csrf_checks = True
            return shipping_rule(request, self.rule.pk).status_code
        def run(action):
            connections.close_all()
            try:
                gate.wait(timeout=10)
                return action()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            checkout_result, edit_result = list(executor.map(run, (purchase, edit)))
        self.assertEqual(edit_result, 200)
        if isinstance(checkout_result, int):
            self.assertEqual(Order.objects.get(pk=checkout_result).grand_total_toman, approved["estimated_total_toman"])
        else:
            self.assertEqual(checkout_result, "quote_changed")
            self.assertFalse(Order.objects.exists())
