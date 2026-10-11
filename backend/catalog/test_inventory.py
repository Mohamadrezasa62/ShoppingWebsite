import importlib
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection, transaction
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from commerce import tests as commerce_fixtures
from commerce.models import Address, Cart, CartLine, ShippingRule
from commerce.services import create_order, cancel_unpaid_order, expire_order, CheckoutError
from commerce.returns import create_line_return, transition_return, refund_sandbox_return
from commerce.cancellations import request_cancellation, review_cancellation, refund_sandbox_cancellation
from payments.orchestration import initiate_sandbox, simulate_result
from sellers.models import SellerMembership, Seller
from operations.invariants import inspect_commerce
from .models import Offer, Warehouse, StockBalance, StockReservation, StockMovement
from .inventory import activate, InventoryError


@override_settings(DEBUG=True, ENABLE_SANDBOX_PAYMENTS=True)
class WarehouseInventoryTests(TestCase):
    def setUp(self):
        commerce_fixtures.CartTests.setUp(self)
        self.offer.reserved_quantity = 0
        self.offer.save(update_fields=["reserved_quantity"])
        self.owner = self.other
        self.seller = self.offer.seller
        SellerMembership.objects.create(seller=self.seller, user=self.owner, role="owner")
        self.address = Address.objects.create(user=self.user, full_name="Buyer", phone=self.user.phone, province="Tehran", city="Tehran", street="Main street", postal_code="1234567890")
        ShippingRule.objects.create(province="Tehran", fulfillment="seller", fee_toman=1000, min_days=1, max_days=2)
        self.base = f"/api/v1/seller/stores/{self.seller.pk}/"
        self.client.force_login(self.owner)

    def post(self, path, data):
        return self.client.post(self.base + path, json.dumps(data), content_type="application/json")

    def initialize(self):
        activate(self.offer.pk, self.owner)
        self.offer.refresh_from_db()
        self.primary = Warehouse.objects.get(seller=self.seller, is_default=True)
        self.secondary = Warehouse.objects.create(seller=self.seller, name="Second warehouse", code="second")
        data = {"source_id": self.primary.pk, "destination_id": self.secondary.pk, "quantity": 3, "request_key": str(uuid4()), "reason": "Move free inventory"}
        self.assertEqual(self.post(f"inventory/{self.offer.pk}/transfer/", data).status_code, 200)
        return data

    def checkout(self, quantity=3):
        cart, _ = Cart.objects.get_or_create(user=self.user)
        CartLine.objects.create(cart=cart, offer=self.offer, quantity=quantity)
        order, created = create_order(self.user, self.address.pk, uuid4())
        self.assertTrue(created)
        return order, order.deliveries.get().lines.get()

    def capture(self, order):
        attempt = initiate_sandbox(self.user, order.pk, uuid4())
        simulate_result(self.user, attempt.pk, "success")
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        return attempt

    def totals(self):
        self.offer.refresh_from_db()
        rows = list(StockBalance.objects.filter(offer=self.offer).order_by("pk"))
        self.assertEqual(self.offer.available_quantity, sum(row.quantity for row in rows))
        self.assertEqual(self.offer.reserved_quantity, sum(row.reserved_quantity for row in rows))
        return [(row.quantity, row.reserved_quantity) for row in rows]

    def test_checkout_splits_reservations_capture_consumes_and_returns_to_source(self):
        self.initialize()
        order, line = self.checkout()
        self.assertEqual(self.totals(), [(1, 1), (3, 2)])
        self.assertEqual(StockReservation.objects.filter(order_line=line).count(), 2)
        self.capture(order)
        self.assertEqual(self.totals(), [(0, 0), (1, 0)])
        delivery = order.deliveries.get()
        delivery.status = "delivered"
        delivery.save(update_fields=["status"])
        case = create_line_return(self.user, delivery.pk, line.pk, 1, "Wrong size")
        transition_return(case.pk, "approved")
        transition_return(case.pk, "received", restock=True)
        self.assertEqual(self.totals(), [(1, 0), (1, 0)])
        refund_sandbox_return(case.pk)
        refund_sandbox_return(case.pk)
        second = create_line_return(self.user, delivery.pk, line.pk, 2, "Remaining items wrong")
        transition_return(second.pk, "approved")
        transition_return(second.pk, "received", restock=True)
        self.assertEqual(self.totals(), [(1, 0), (3, 0)])
        self.assertEqual(list(StockReservation.objects.filter(order_line=line).order_by("balance_id").values_list("restocked_quantity", flat=True)), [1, 2])
        report = inspect_commerce()
        self.assertTrue(report["consistent"], report["issues"])

    def test_cancel_and_expiry_release_exact_allocations_once(self):
        self.initialize()
        order, line = self.checkout()
        cancel_unpaid_order(order.pk, self.user)
        cancel_unpaid_order(order.pk, self.user)
        self.assertEqual(self.totals(), [(1, 0), (3, 0)])
        self.assertEqual(set(StockReservation.objects.filter(order_line=line).values_list("status", flat=True)), {"released"})
        second, _ = self.checkout()
        self.assertTrue(expire_order(second.pk, second.expires_at + timedelta(seconds=1)))
        self.assertFalse(expire_order(second.pk, second.expires_at + timedelta(seconds=2)))
        self.assertEqual(self.totals(), [(1, 0), (3, 0)])
        self.assertTrue(inspect_commerce()["consistent"])

    def test_pre_activation_paid_return_is_explicitly_unattributed_to_default(self):
        order, line = self.checkout()
        self.capture(order)
        activate(self.offer.pk, self.owner)
        delivery = order.deliveries.get()
        delivery.status = "delivered"
        delivery.save(update_fields=["status"])
        case = create_line_return(self.user, delivery.pk, line.pk, 1, "Wrong size")
        transition_return(case.pk, "approved")
        transition_return(case.pk, "received", restock=True)
        self.assertEqual(self.totals(), [(2, 0)])
        self.assertEqual(StockMovement.objects.filter(kind="legacy_restock", order_line=line).count(), 1)
        self.assertFalse(StockReservation.objects.filter(order_line=line).exists())
        self.assertTrue(inspect_commerce()["consistent"])

    def test_capture_records_cash_for_review_when_warehouse_allocation_is_missing(self):
        self.initialize()
        order, line = self.checkout()
        StockReservation.objects.filter(order_line=line).delete()
        attempt = initiate_sandbox(self.user, order.pk, uuid4())
        attempt = simulate_result(self.user, attempt.pk, "success")
        self.assertEqual(attempt.status, "review_required")
        order.refresh_from_db()
        self.assertEqual(order.status, "pending_payment")
        self.assertEqual(self.totals(), [(1, 1), (3, 2)])
        codes = {row["code"] for row in inspect_commerce()["issues"]}
        self.assertIn("warehouse_line_allocation_mismatch", codes)

    def test_paid_cancellation_restocks_each_source_once(self):
        self.initialize()
        order, line = self.checkout()
        self.capture(order)
        delivery = order.deliveries.get()
        case = request_cancellation(self.user, delivery.pk, "No longer needed")
        review_cancellation(case.pk, "approved", self.owner, "Approved request")
        refund_sandbox_cancellation(case.pk)
        refund_sandbox_cancellation(case.pk)
        self.assertEqual(self.totals(), [(1, 0), (3, 0)])
        self.assertEqual(StockMovement.objects.filter(kind="restock").count(), 2)
        self.assertTrue(inspect_commerce()["consistent"])

    def test_versions_reserved_stock_and_seller_isolation(self):
        self.initialize()
        order, _ = self.checkout()
        balance = StockBalance.objects.get(offer=self.offer, warehouse=self.primary)
        path = f"inventory/{self.offer.pk}/adjust/"
        data = {"warehouse_id": self.primary.pk, "quantity": 0, "version": balance.version, "reason": "Recount stock"}
        self.assertEqual(self.post(path, data).status_code, 409)
        data["quantity"] = 2
        self.assertEqual(self.post(path, data).status_code, 200)
        self.assertEqual(self.post(path, data).status_code, 409)
        other_seller = Seller.objects.create(name="Other", status="approved")
        foreign = Warehouse.objects.create(seller=other_seller, name="Private", code="private")
        self.assertEqual(self.post(path, {**data, "warehouse_id": foreign.pk, "version": 0}).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.base + "inventory/").status_code, 404)
        self.assertEqual(self.post(path, data).status_code, 404)
        self.assertEqual(StockBalance.objects.filter(warehouse=foreign).count(), 0)
        cancel_unpaid_order(order.pk, self.user)

    def test_transfer_deduplication_and_reserved_stock_are_preserved(self):
        data = self.initialize()
        self.assertEqual(self.post(f"inventory/{self.offer.pk}/transfer/", data).status_code, 200)
        self.assertEqual(self.post(f"inventory/{self.offer.pk}/transfer/", {**data, "quantity": 2}).status_code, 409)
        self.assertEqual(self.totals(), [(1, 0), (3, 0)])
        self.checkout()
        self.assertEqual(self.post(f"inventory/{self.offer.pk}/transfer/", {**data, "request_key": str(uuid4()), "quantity": 1}).status_code, 409)
        self.assertEqual(self.totals(), [(1, 1), (3, 2)])

    def test_single_stock_api_cannot_overwrite_multiwarehouse_totals(self):
        self.initialize()
        url = self.base + f"offers/{self.offer.pk}/"
        response = self.client.patch(url, json.dumps({"price_toman": 12000, "available_quantity": 7}), content_type="application/json")
        self.assertEqual(response.status_code, 409)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.price_toman, 10000)
        self.assertEqual(self.offer.available_quantity, 4)
        self.assertEqual(self.client.patch(url, json.dumps({"price_toman": 12000}), content_type="application/json").status_code, 200)

    def test_audit_failure_rolls_back_balance_history_and_cache(self):
        self.initialize()
        balance = StockBalance.objects.get(offer=self.offer, warehouse=self.primary)
        before_count = StockMovement.objects.count()
        with patch("sellers.inventory_views._audit", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.post(f"inventory/{self.offer.pk}/adjust/", {"warehouse_id": self.primary.pk, "quantity": 5, "version": balance.version, "reason": "Recount"})
        self.assertEqual(self.totals(), [(1, 0), (3, 0)])
        self.assertEqual(StockMovement.objects.count(), before_count)

    def test_staff_inventory_visibility_requires_marketplace_role(self):
        self.initialize()
        path = "/api/v1/operations/inventory/"
        self.assertEqual(self.client.get(path, {"seller_id": self.seller.pk}).status_code, 403)
        staff = get_user_model().objects.create_user("09123456588", is_staff=True)
        staff.groups.add(Group.objects.get_or_create(name="support_agent")[0])
        self.client.force_login(staff)
        self.assertEqual(self.client.get(path, {"seller_id": self.seller.pk}).status_code, 403)
        staff.groups.add(Group.objects.get_or_create(name="marketplace_manager")[0])
        response = self.client.get(path, {"seller_id": self.seller.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["offers"][0]["balances"]), 2)
        self.assertNotIn("contact_phone", response.content.decode())
        self.assertEqual(self.client.get(path, {"seller_id": "bad"}).status_code, 400)

    def test_warehouse_owner_approval_and_deactivation_guards(self):
        self.initialize()
        self.assertEqual(self.post("warehouses/", {"name": "Third warehouse", "code": "third", "reason": "New location"}).status_code, 201)
        self.assertEqual(self.post("warehouses/", {"name": "Duplicate", "code": "third", "reason": "New location"}).status_code, 409)
        for warehouse in (self.primary, self.secondary):
            response = self.client.patch(self.base + f"warehouses/{warehouse.pk}/", json.dumps({"name": warehouse.name, "active": False, "reason": "Closing warehouse"}), content_type="application/json")
            self.assertEqual(response.status_code, 409)
        SellerMembership.objects.filter(user=self.owner).update(role="staff")
        self.assertEqual(self.post("warehouses/", {"name": "Forbidden", "code": "forbidden", "reason": "New location"}).status_code, 403)
        self.seller.status = "suspended"
        self.seller.save(update_fields=["status"])
        self.assertEqual(self.post(f"inventory/{self.offer.pk}/activate/", {"reason": "Activate stock"}).status_code, 403)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.base + "warehouses/", json.dumps({}), content_type="application/json").status_code, 403)

    def test_corruption_blocks_checkout_and_is_reported_without_repair(self):
        self.initialize()
        primary = StockBalance.objects.get(offer=self.offer, warehouse=self.primary)
        StockBalance.objects.filter(pk=primary.pk).update(quantity=2)
        with self.assertRaises(CheckoutError):
            self.checkout()
        codes = {item["code"] for item in inspect_commerce()["issues"]}
        self.assertIn("warehouse_cache_mismatch", codes)
        self.assertIn("warehouse_history_or_reservation_mismatch", codes)
        primary.refresh_from_db()
        self.assertEqual(primary.quantity, 2)

    def test_data_bootstrap_migrates_pending_reservations_and_rejects_corruption(self):
        order, line = self.checkout(quantity=2)
        migration = importlib.import_module("catalog.migrations.0013_bootstrap_warehouse_inventory")
        migration.bootstrap(apps, SimpleNamespace(connection=connection))
        self.offer.refresh_from_db()
        self.assertTrue(self.offer.inventory_managed)
        self.assertEqual(StockReservation.objects.get(order_line=line).quantity, 2)
        cancel_unpaid_order(order.pk, self.user)
        self.assertEqual(self.totals(), [(4, 0)])
        second = Offer.objects.create(variant=self.offer.variant, seller=Seller.objects.create(name="Second"), price_toman=1, available_quantity=2, reserved_quantity=1)
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                migration.bootstrap(apps, SimpleNamespace(connection=connection))
        second.refresh_from_db()
        self.assertFalse(second.inventory_managed)
        self.assertFalse(StockBalance.objects.filter(offer=second).exists())
