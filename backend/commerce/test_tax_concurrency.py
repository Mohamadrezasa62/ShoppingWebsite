import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase, RequestFactory
from operations.tax_api import rule
from . import test_taxes as fixtures
from .models import Order, TaxRule
from .services import create_order, CheckoutError


@skipUnless(connection.vendor == "postgresql", "Tax rule parent-row serialization requires PostgreSQL")
class TaxConcurrencyTests(TransactionTestCase):
    setUpBase = fixtures.TaxTests.setUpBase
    setUp = fixtures.TaxTests.setUp
    preview = fixtures.TaxTests.preview

    def race(self, first, second):
        gate = Barrier(2)
        def run(action):
            connections.close_all()
            try:
                gate.wait(timeout=10)
                return action()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, (first, second)))

    def assert_serialized_change(self):
        # Same staff buyer exercises account/audit FK lock ordering as well.
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.user.groups.add(*self.admin.groups.all())
        quote = self.preview()
        old_tax = quote["tax_total_toman"]
        def purchase():
            try:
                return create_order(get_user_model().objects.get(pk=self.user.pk), self.address.pk, uuid4(), quote["approval_token"])[0].pk
            except CheckoutError as error:
                return error.code
        def edit():
            request = RequestFactory().put("/tax-test/", json.dumps({"label": "Changed tax", "rate_bps": 2000, "is_active": True, "reason": "Test serialized policy"}), content_type="application/json")
            request.user = get_user_model().objects.get(pk=self.user.pk)
            request._dont_enforce_csrf_checks = True
            return rule(request, self.category.pk).status_code
        result, changed = self.race(purchase, edit)
        self.assertEqual(changed, 200)
        self.assertEqual(TaxRule.objects.get(category=self.category).rate_bps, 2000)
        if type(result) is int:
            self.assertEqual(Order.objects.get(pk=result).tax_total_toman, old_tax)
        else:
            self.assertEqual(result, "quote_changed")
            self.assertFalse(Order.objects.exists())
            self.offer.refresh_from_db()
            self.assertEqual(self.offer.reserved_quantity, 0)

    def test_rate_edit_and_checkout_serialize(self):
        self.assert_serialized_change()

    def test_first_rule_creation_and_checkout_serialize(self):
        self.tax.delete()
        self.assert_serialized_change()
