import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.utils import timezone
from . import test_quotes as fixtures
from .models import ShippingMethod, DeliverySlot, ShippingRule, CartLine, Cart, Order
from .shipping import booking_count
from .services import cancel_unpaid_order, expire_order
from catalog.models import Offer
from sellers.models import Seller
from operations.invariants import inspect_commerce


class ShippingChoiceTests(TestCase):
    setUpBase = fixtures.QuoteApprovalTests.setUp

    def setUp(self):
        self.setUpBase()
        self.admin = get_user_model().objects.create_user("09123456301", is_staff=True)
        self.admin.groups.add(Group.objects.create(name="marketplace_manager"))
        self.method = ShippingMethod.objects.create(rule=self.rule, code="express", label="Express", fee_toman=3000, min_days=1, max_days=2)
        self.key = f"{self.offer.seller_id}:seller"
        self.methods = {self.key: self.method.pk}
        self.slot = DeliverySlot.objects.create(method=self.method, starts_at=timezone.now()+timedelta(days=3), ends_at=timezone.now()+timedelta(days=3,hours=2), capacity=1)
        self.slots = {self.key: self.slot.pk}

    def preview(self, methods=None, slots=None):
        return self.client.get("/api/v1/commerce/quote/", {"address_id": self.address.pk, "shipping_methods": json.dumps(self.methods if methods is None else methods), "shipping_slots": json.dumps(self.slots if slots is None else slots)})

    def checkout(self, quote, methods=None, slots=None, key=None):
        return self.client.post("/api/v1/commerce/checkout/", json.dumps({"address_id": self.address.pk, "idempotency_key": str(key or uuid4()), "quote_token": quote["approval_token"], "shipping_methods": self.methods if methods is None else methods, "shipping_slots": self.slots if slots is None else slots}), content_type="application/json")

    def test_method_and_window_snapshots_match_approval_and_retry(self):
        quote = self.preview().json()["quote"]
        self.assertEqual(quote["shipping_total_toman"], 3000)
        self.assertEqual(booking_count(self.slot), 0)
        request_key = uuid4()
        created = self.checkout(quote, key=request_key)
        self.assertEqual(created.status_code, 201)
        delivery = created.json()["order"]["deliveries"][0]
        self.assertEqual(delivery["shipping_method_code"], "express")
        self.assertEqual(delivery["shipping_method_label"], "Express")
        self.assertEqual(delivery["delivery_window_start"], quote["deliveries"][0]["window"]["starts_at"])
        self.assertEqual(booking_count(self.slot), 1)
        self.assertEqual(self.checkout(quote, key=request_key).status_code, 200)
        self.assertEqual(self.checkout(quote, methods={}, slots={}, key=request_key).json()["error"], "idempotency_conflict")
        self.assertTrue(inspect_commerce()["consistent"])

    def test_method_price_change_requires_reapproval_without_reserving(self):
        quote = self.preview().json()["quote"]
        self.method.fee_toman = 4000
        self.method.save(update_fields=["fee_toman"])
        self.assertEqual(self.checkout(quote).json()["error"], "quote_changed")
        self.assertEqual(booking_count(self.slot), 0)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.reserved_quantity, 0)
        self.assertTrue(CartLine.objects.filter(cart=self.cart).exists())

    def test_inactive_cross_province_and_foreign_group_methods_rejected(self):
        foreign_rule = ShippingRule.objects.create(province="Other", fee_toman=1000, min_days=2, max_days=3)
        foreign = ShippingMethod.objects.create(rule=foreign_rule, code="other", label="Other", fee_toman=1000, min_days=1, max_days=3)
        self.assertEqual(self.preview({self.key: foreign.pk}, {}).status_code, 409)
        self.assertEqual(self.preview({"999999:seller": self.method.pk}, {}).status_code, 409)
        self.method.is_active = False
        self.method.save(update_fields=["is_active"])
        self.assertEqual(self.preview(slots={}).json()["error"], "shipping_method_unavailable")
        default = self.preview({}, {}).json()["quote"]
        self.assertEqual(default["shipping_total_toman"], self.rule.fee_toman)

    def test_cancellation_and_expiration_free_capacity_exactly_once(self):
        created = self.checkout(self.preview().json()["quote"])
        order = Order.objects.get(pk=created.json()["order"]["id"])
        cancel_unpaid_order(order.pk, self.user)
        cancel_unpaid_order(order.pk, self.user)
        self.assertEqual(booking_count(self.slot), 0)
        self.client.force_login(self.admin)
        path = f"/api/v1/operations/delivery-slots/{self.slot.pk}/"
        self.assertEqual(self.client.patch(path, json.dumps({"starts_at": (self.slot.starts_at+timedelta(minutes=1)).isoformat(), "reason": "Move cancelled window"}), content_type="application/json").status_code, 400)
        self.client.force_login(self.user)
        CartLine.objects.create(cart=self.cart, offer=self.offer, quantity=2)
        created = self.checkout(self.preview().json()["quote"])
        order = Order.objects.get(pk=created.json()["order"]["id"])
        self.assertTrue(expire_order(order.pk, now=order.expires_at+timedelta(seconds=1)))
        self.assertFalse(expire_order(order.pk, now=order.expires_at+timedelta(seconds=1)))
        self.assertEqual(booking_count(self.slot), 0)

    def test_two_sellers_using_same_window_need_two_capacity_units(self):
        seller = Seller.objects.create(name="Second", status="approved")
        offer = Offer.objects.create(variant=self.offer.variant, seller=seller, price_toman=12000, available_quantity=5, status="active")
        CartLine.objects.create(cart=self.cart, offer=offer, quantity=1)
        methods = {**self.methods, f"{seller.pk}:seller": self.method.pk}
        slots = {**self.slots, f"{seller.pk}:seller": self.slot.pk}
        self.assertEqual(self.preview(methods, slots).json()["error"], "shipping_slot_unavailable")
        self.slot.capacity = 2
        self.slot.save(update_fields=["capacity"])
        quote = self.preview(methods, slots).json()["quote"]
        self.assertEqual(quote["shipping_total_toman"], 6000)
        self.assertEqual(self.checkout(quote, methods, slots).status_code, 201)
        self.assertEqual(booking_count(self.slot), 2)

    def test_expired_inactive_foreign_window_and_capacity_change_reject_stale_approval(self):
        quote = self.preview().json()["quote"]
        self.slot.is_active = False
        self.slot.save(update_fields=["is_active"])
        self.assertEqual(self.checkout(quote).json()["error"], "shipping_slot_unavailable")
        self.slot.is_active = True
        self.slot.starts_at = timezone.now()-timedelta(hours=1)
        self.slot.save(update_fields=["is_active", "starts_at"])
        self.assertEqual(self.checkout(quote).json()["error"], "shipping_slot_unavailable")
        self.assertEqual(self.preview({self.key: 0}).status_code, 409)
        self.assertFalse(Order.objects.exists())

    def test_admin_roles_csrf_validation_and_audit_rollback(self):
        path = f"/api/v1/operations/shipping-rules/{self.rule.pk}/methods/"
        payload = {"code": "slow", "label": "Economy", "fee_toman": 900, "min_days": 3, "max_days": 5, "is_active": True, "reason": "Reviewed delivery method"}
        self.assertEqual(self.client.post(path, json.dumps(payload), content_type="application/json").status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(path, json.dumps(payload), content_type="application/json").status_code, 201)
        self.assertEqual(self.client.post(path, json.dumps(payload), content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(path, json.dumps({**payload, "code": "standard"}), content_type="application/json").status_code, 400)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(path, json.dumps(payload), content_type="application/json").status_code, 403)
        edit = f"/api/v1/operations/shipping-methods/{self.method.pk}/"
        with patch("operations.shipping_method_api._audit", side_effect=RuntimeError("Audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.patch(edit, json.dumps({"fee_toman": 5000, "reason": "Update rate"}), content_type="application/json")
        self.method.refresh_from_db()
        self.assertEqual(self.method.fee_toman, 3000)

    def test_booked_window_cannot_move_or_reduce_capacity_below_bookings(self):
        self.assertEqual(self.checkout(self.preview().json()["quote"]).status_code, 201)
        self.client.force_login(self.admin)
        path = f"/api/v1/operations/delivery-slots/{self.slot.pk}/"
        for payload in [{"capacity": 0}, {"starts_at": (self.slot.starts_at+timedelta(minutes=1)).isoformat()}]:
            self.assertEqual(self.client.patch(path, json.dumps({**payload, "reason": "Reviewed edit"}), content_type="application/json").status_code, 400)
        self.assertEqual(self.client.patch(path, json.dumps({"is_active": False, "reason": "Stop new bookings"}), content_type="application/json").status_code, 200)
        self.assertEqual(booking_count(self.slot), 1)
        self.assertTrue(inspect_commerce()["consistent"])

    def test_slot_creation_requires_timezone_future_window_and_capacity(self):
        self.client.force_login(self.admin)
        path = f"/api/v1/operations/shipping-methods/{self.method.pk}/slots/"
        payload = {"starts_at": (timezone.now()+timedelta(days=4)).isoformat(), "ends_at": (timezone.now()+timedelta(days=4,hours=2)).isoformat(), "capacity": 5, "is_active": True, "reason": "Reviewed service window"}
        self.assertEqual(self.client.post(path, json.dumps(payload), content_type="application/json").status_code, 201)
        for change in [{"starts_at": "2026-01-01T12:00:00"}, {"capacity": True}, {"ends_at": (timezone.now()+timedelta(days=100)).isoformat()}]:
            self.assertEqual(self.client.post(path, json.dumps({**payload, **change}), content_type="application/json").status_code, 400)

    def test_checker_reports_capacity_and_window_corruption_without_repair(self):
        self.assertEqual(self.checkout(self.preview().json()["quote"]).status_code, 201)
        DeliverySlot.objects.filter(pk=self.slot.pk).update(starts_at=self.slot.starts_at+timedelta(minutes=1))
        report = inspect_commerce()
        self.assertFalse(report["consistent"])
        self.assertIn("delivery_window_snapshot_mismatch", [issue["code"] for issue in report["issues"]])
