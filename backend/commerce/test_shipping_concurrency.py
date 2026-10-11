import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase, RequestFactory
from operations.delivery_slot_api import update
from . import test_shipping_choices as fixtures
from .models import Address, Cart, CartLine, Order
from .services import create_order, CheckoutError
from .shipping import booking_count
from catalog.models import Offer, Variant


@skipUnless(connection.vendor == "postgresql", "Delivery window capacity locks require PostgreSQL")
class ShippingCapacityConcurrencyTests(TransactionTestCase):
    setUpBase = fixtures.ShippingChoiceTests.setUpBase
    setUp = fixtures.ShippingChoiceTests.setUp
    preview = fixtures.ShippingChoiceTests.preview

    def race(self, first, second):
        gate = Barrier(2)
        def run(action):
            connections.close_all()
            try:
                gate.wait(timeout=10)
                return action()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(run, (first, second)))

    def purchase(self, user_id, address_id, token):
        try:
            user = get_user_model().objects.get(pk=user_id)
            return create_order(user, address_id, uuid4(), token, self.methods, self.slots)[0].pk
        except CheckoutError as error:
            return error.code

    def test_two_buyers_with_distinct_offer_locks_cannot_take_last_window(self):
        first_token = self.preview().json()["quote"]["approval_token"]
        variant = Variant.objects.create(product=self.offer.variant.product, sku="SECOND-WINDOW-OFFER")
        offer = Offer.objects.create(variant=variant, seller=self.offer.seller, price_toman=11000, available_quantity=5, status="active")
        other_cart = Cart.objects.create(user=self.other)
        CartLine.objects.create(cart=other_cart, offer=offer, quantity=1)
        address = Address.objects.create(user=self.other, full_name="Other buyer", phone=self.other.phone, province="Tehran", city="Tehran", street="Street", postal_code="1234567890")
        self.client.force_login(self.other)
        response = self.client.get("/api/v1/commerce/quote/", {"address_id": address.pk, "shipping_methods": json.dumps(self.methods), "shipping_slots": json.dumps(self.slots)})
        second_token = response.json()["quote"]["approval_token"]
        results = self.race(lambda: self.purchase(self.user.pk, self.address.pk, first_token), lambda: self.purchase(self.other.pk, address.pk, second_token))
        self.assertEqual(sum(type(result) is int for result in results), 1)
        self.assertIn("shipping_slot_unavailable", results)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(booking_count(self.slot), 1)

    def test_window_deactivation_and_checkout_preserve_original_reservation(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.user.groups.add(*self.admin.groups.all())
        token = self.preview().json()["quote"]["approval_token"]
        def deactivate():
            request = RequestFactory().patch("/slot-test/", json.dumps({"is_active": False, "reason": "Stop new booking"}), content_type="application/json")
            request.user = get_user_model().objects.get(pk=self.user.pk)
            request._dont_enforce_csrf_checks = True
            return update(request, self.slot.pk).status_code
        result, changed = self.race(lambda: self.purchase(self.user.pk, self.address.pk, token), deactivate)
        self.assertEqual(changed, 200)
        self.slot.refresh_from_db()
        self.assertFalse(self.slot.is_active)
        if type(result) is int:
            self.assertEqual(booking_count(self.slot), 1)
        else:
            self.assertEqual(result, "shipping_slot_unavailable")
            self.assertEqual(booking_count(self.slot), 0)
