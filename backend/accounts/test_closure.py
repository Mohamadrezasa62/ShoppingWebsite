import json
from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from accounts.closure import ClosureError, decide_closure, request_closure
from accounts.models import AccountClosure
from commerce.models import Order
from commerce.services import CheckoutError, create_order
from operations.models import AuditEvent
from sellers.models import Seller, SellerMembership


class AccountClosureTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("09123456861")
        self.other = get_user_model().objects.create_user("09123456862")
        self.admin = get_user_model().objects.create_user("09123456863", is_staff=True)
        self.admin.groups.add(Group.objects.create(name="system_administrator"))
        self.client.force_login(self.user)

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def test_private_idempotent_request_and_withdrawal(self):
        path = "/api/v1/auth/closure-requests/"
        first = self.post(path, {"reason": "Close my account"})
        self.assertEqual(first.status_code, 200)
        pk = first.json()["request"]["id"]
        self.assertEqual(self.post(path, {"reason": "Close my account"}).json()["request"]["id"], pk)
        self.assertEqual(self.post(path, {"reason": "Different reason"}).status_code, 409)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(path).json()["requests"], [])
        self.assertEqual(self.post(f"{path}{pk}/withdraw/", {}).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.post(f"{path}{pk}/withdraw/", {}).json()["request"]["status"], "withdrawn")
        self.assertEqual(self.post(f"{path}{pk}/withdraw/", {}).status_code, 200)
        self.assertEqual(self.post(path, {"reason": "Request again"}).status_code, 200)
        self.assertEqual(AuditEvent.objects.filter(action="account_closure_withdrawn").count(), 1)

    def test_deactivation_revokes_sessions_and_prevents_stale_checkout(self):
        device = Client()
        device.force_login(self.user)
        case = request_closure(self.user, "Close my account")
        decide_closure(case.pk, "completed", self.admin, "Verified customer request")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.user.session_version, 1)
        self.assertFalse(self.user.has_usable_password())
        self.assertEqual(device.get("/api/v1/auth/me/").status_code, 401)
        with self.assertRaises(CheckoutError) as caught:
            create_order(self.user, 1, uuid4())
        self.assertEqual(caught.exception.code, "account_unavailable")
        from commerce.returns import create_line_return
        with self.assertRaises(CheckoutError) as caught:
            create_line_return(self.user, 1, 1, 1, "Return request")
        self.assertEqual(caught.exception.code, "account_unavailable")

    def test_open_order_blocks_closure_and_snapshots_are_retained(self):
        from django.utils import timezone
        order = Order.objects.create(user=self.user, idempotency_key=uuid4(), address_snapshot={"full_name": "Retained buyer"}, item_total_toman=100, shipping_total_toman=0, grand_total_toman=100, expires_at=timezone.now())
        case = request_closure(self.user, "Close my account")
        with self.assertRaises(ClosureError):
            decide_closure(case.pk, "completed", self.admin, "Verified request")
        case.refresh_from_db()
        self.assertEqual(case.status, "requested")
        order.status = "expired"
        order.save(update_fields=["status"])
        decide_closure(case.pk, "completed", self.admin, "Verified request")
        order.refresh_from_db()
        self.assertEqual(order.address_snapshot, {"full_name": "Retained buyer"})
        self.assertEqual(order.grand_total_toman, 100)

    def test_staff_and_seller_require_separate_offboarding(self):
        seller = Seller.objects.create(name="Seller")
        SellerMembership.objects.create(user=self.user, seller=seller, role="owner")
        for user in [self.admin, self.user]:
            with self.assertRaises(ClosureError) as caught:
                request_closure(user, "Close account")
            self.assertEqual(caught.exception.code, "protected_account")
        self.assertFalse(AccountClosure.objects.exists())

    def test_paid_delivery_and_open_return_block_completion(self):
        from django.utils import timezone
        from commerce.models import OrderDelivery, ReturnCase
        seller = Seller.objects.create(name="Store")
        order = Order.objects.create(user=self.user, status="paid", idempotency_key=uuid4(), address_snapshot={}, item_total_toman=100, shipping_total_toman=0, grand_total_toman=100, expires_at=timezone.now())
        delivery = OrderDelivery.objects.create(order=order, seller=seller, seller_name="Store", fulfillment="seller", shipping_fee_toman=0, min_days=1, max_days=2)
        case = request_closure(self.user, "Close account")
        with self.assertRaises(ClosureError):
            decide_closure(case.pk, "completed", self.admin, "Verified request")
        delivery.status = "delivered"
        delivery.save(update_fields=["status"])
        returned = ReturnCase.objects.create(delivery=delivery, requested_by=self.user, reason="Damaged", requested_amount_toman=100)
        with self.assertRaises(ClosureError):
            decide_closure(case.pk, "completed", self.admin, "Verified request")
        returned.status = "refunded"
        returned.save(update_fields=["status"])
        decide_closure(case.pk, "completed", self.admin, "Verified request")

    def test_new_membership_blocks_completion(self):
        case = request_closure(self.user, "Close account")
        seller = Seller.objects.create(name="Seller")
        SellerMembership.objects.create(user=self.user, seller=seller, role="owner")
        with self.assertRaises(ClosureError):
            decide_closure(case.pk, "completed", self.admin, "Verified request")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_review_roles_csrf_and_final_state(self):
        case = request_closure(self.user, "Close account")
        path = f"/api/v1/operations/account-closures/{case.pk}/decision/"
        self.assertEqual(self.post(path, {"status": "completed", "reason": "Verified request"}).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(path, "{}", content_type="application/json").status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.post(path, {"status": "rejected", "reason": "Clarification required"}).status_code, 200)
        self.assertEqual(self.post(path, {"status": "completed", "reason": "Verified request"}).status_code, 409)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_audit_failure_rolls_back_deactivation(self):
        case = request_closure(self.user, "Close account")
        with patch("accounts.closure.audit", side_effect=RuntimeError("Audit unavailable")):
            with self.assertRaises(RuntimeError):
                decide_closure(case.pk, "completed", self.admin, "Verified request")
        self.user.refresh_from_db()
        case.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.session_version, 0)
        self.assertEqual(case.status, "requested")
