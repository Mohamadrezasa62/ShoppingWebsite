import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase, RequestFactory, override_settings
from commerce.models import Cart, CartLine
from commerce.services import create_order, CheckoutError
from commerce.returns import create_line_return, transition_return
from operations.invariants import inspect_commerce
from sellers import inventory_views
from sellers.models import SellerMembership
from . import test_inventory as fixtures
from .inventory import activate
from .models import Warehouse, StockBalance


@skipUnless(connection.vendor == "postgresql", "Warehouse allocation row locking requires PostgreSQL")
@override_settings(DEBUG=True, ENABLE_SANDBOX_PAYMENTS=True)
class WarehouseConcurrencyTests(TransactionTestCase):
    post = fixtures.WarehouseInventoryTests.post
    capture = fixtures.WarehouseInventoryTests.capture

    def setUp(self):
        fixtures.WarehouseInventoryTests.setUp(self)
        self.offer.available_quantity = 1
        self.offer.save(update_fields=["available_quantity"])
        activate(self.offer.pk, self.owner)
        self.primary = Warehouse.objects.get(seller=self.seller, is_default=True)
        self.secondary = Warehouse.objects.create(seller=self.seller, name="Second", code="second")
        cart = Cart.objects.create(user=self.user)
        CartLine.objects.create(cart=cart, offer=self.offer, quantity=1)

    def request(self, function, payload, **kwargs):
        request = RequestFactory().post("/inventory-test/", json.dumps(payload), content_type="application/json")
        request.user = get_user_model().objects.get(pk=self.owner.pk)
        request._dont_enforce_csrf_checks = True
        return function(request, seller_id=self.seller.pk, **kwargs).status_code

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

    def checkout(self):
        user = get_user_model().objects.get(pk=self.user.pk)
        try:
            return create_order(user, self.address.pk, uuid4())[0].pk
        except CheckoutError as exc:
            return exc.code

    def test_transfer_and_checkout_preserve_the_single_physical_unit(self):
        payload = {"source_id": self.primary.pk, "destination_id": self.secondary.pk, "quantity": 1, "request_key": str(uuid4()), "reason": "Move stock"}
        transfer_result, order_id = self.race(lambda: self.request(inventory_views.transfer, payload, offer_id=self.offer.pk), self.checkout)
        self.assertIsInstance(order_id, int)
        self.assertIn(transfer_result, (200, 409))
        self.offer.refresh_from_db()
        self.assertEqual((self.offer.available_quantity, self.offer.reserved_quantity), (1, 1))
        self.assertTrue(inspect_commerce()["consistent"])

    def test_owner_checkout_and_zero_adjustment_serialize_without_actor_fk_deadlock(self):
        SellerMembership.objects.create(seller=self.seller, user=self.user, role="owner")
        self.owner = self.user
        balance = StockBalance.objects.get(offer=self.offer)
        payload = {"warehouse_id": self.primary.pk, "quantity": 0, "version": balance.version, "reason": "Recount zero"}
        adjustment_result, checkout_result = self.race(lambda: self.request(inventory_views.adjust, payload, offer_id=self.offer.pk), self.checkout)
        if adjustment_result == 200:
            self.assertEqual(checkout_result, "offer_unavailable")
        else:
            self.assertEqual(adjustment_result, 409)
            self.assertIsInstance(checkout_result, int)
        self.assertTrue(inspect_commerce()["consistent"])

    def test_deactivation_cannot_race_a_return_into_inactive_stock(self):
        payload = {"source_id": self.primary.pk, "destination_id": self.secondary.pk, "quantity": 1, "request_key": str(uuid4()), "reason": "Move stock"}
        self.assertEqual(self.post(f"inventory/{self.offer.pk}/transfer/", payload).status_code, 200)
        order, _ = create_order(self.user, self.address.pk, uuid4())
        self.capture(order)
        delivery = order.deliveries.get()
        delivery.status = "delivered"
        delivery.save(update_fields=["status"])
        line = delivery.lines.get()
        case = create_line_return(self.user, delivery.pk, line.pk, 1, "Wrong item")
        transition_return(case.pk, "approved")
        def restock():
            try:
                return transition_return(case.pk, "received", restock=True).status
            except CheckoutError as exc:
                return exc.code
        def deactivate():
            request = RequestFactory().patch("/inventory-test/", json.dumps({"name": "Second", "active": False, "reason": "Close location"}), content_type="application/json")
            request.user = get_user_model().objects.get(pk=self.owner.pk)
            request._dont_enforce_csrf_checks = True
            return inventory_views.warehouse(request, seller_id=self.seller.pk, warehouse_id=self.secondary.pk).status_code
        deactivate_result, restock_result = self.race(deactivate, restock)
        self.secondary.refresh_from_db()
        balance = StockBalance.objects.get(offer=self.offer, warehouse=self.secondary)
        if deactivate_result == 200:
            self.assertFalse(self.secondary.is_active)
            self.assertEqual(balance.quantity, 0)
            self.assertEqual(restock_result, "warehouse_unavailable")
        else:
            self.assertEqual(deactivate_result, 409)
            self.assertTrue(self.secondary.is_active)
            self.assertEqual(balance.quantity, 1)
            self.assertEqual(restock_result, "received")
        self.assertTrue(inspect_commerce()["consistent"])
