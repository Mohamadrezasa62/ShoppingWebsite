import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Sum
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from catalog.models import Category, Product, Variant, Offer
from operations.invariants import inspect_commerce
from operations.models import AuditEvent
from payments.models import LedgerEntry
from payments.finance import accrue_delivery
from payments.orchestration import initiate_sandbox, simulate_result
from sellers.models import Seller
from sellers.reports import seller_performance
from . import test_quotes as fixtures
from .models import TaxRule, CartLine, Coupon, Order, OrderLine, ReturnLine
from .returns import create_line_return, transition_return, refund_sandbox_return
from .cancellations import request_cancellation, review_cancellation, refund_sandbox_cancellation


@override_settings(DEBUG=True, ENABLE_SANDBOX_PAYMENTS=True)
class TaxTests(TestCase):
    setUpBase = fixtures.QuoteApprovalTests.setUp

    def setUp(self):
        self.setUpBase()
        self.category = self.offer.variant.product.category
        self.tax = TaxRule.objects.create(category=self.category, label="Configured test tax", rate_bps=1234, is_active=True)
        self.admin = get_user_model().objects.create_user("09123456182", is_staff=True)
        self.admin.groups.add(Group.objects.create(name="marketplace_manager"))
        self.path = f"/api/v1/operations/categories/{self.category.pk}/tax/"

    def preview(self):
        response = self.client.get("/api/v1/commerce/quote/", {"address_id": self.address.pk})
        self.assertEqual(response.status_code, 200)
        return response.json()["quote"]

    def checkout(self, quote=None, key=None):
        quote = quote or self.preview()
        return self.client.post("/api/v1/commerce/checkout/", json.dumps({"address_id": self.address.pk, "idempotency_key": str(key or uuid4()), "quote_token": quote["approval_token"]}), content_type="application/json")

    def pay(self):
        response = self.checkout()
        self.assertEqual(response.status_code, 201)
        self.order = Order.objects.get(pk=response.json()["order"]["id"])
        self.delivery = self.order.deliveries.get()
        self.order_line = self.delivery.lines.get()
        attempt = initiate_sandbox(self.user, self.order.pk, uuid4())
        simulate_result(self.user, attempt.pk, "success")

    def test_tax_after_coupon_matches_quote_and_snapshots(self):
        coupon = Coupon.objects.create(code="TAXTEST", kind="fixed", value=1001, starts_at=timezone.now()-timedelta(days=1), ends_at=timezone.now()+timedelta(days=1), usage_limit=10, per_user_limit=2)
        self.cart.coupon = coupon
        self.cart.save(update_fields=["coupon"])
        quote = self.preview()
        self.assertEqual(quote["tax_total_toman"], 18999*1234//10000)
        response = self.checkout(quote)
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        line = OrderLine.objects.get()
        self.assertEqual(order.grand_total_toman, quote["estimated_total_toman"])
        self.assertEqual(line.tax_toman, order.tax_total_toman)
        self.assertEqual(line.tax_rate_bps, 1234)
        self.assertEqual(line.tax_label, self.tax.label)
        self.tax.rate_bps = 9999
        self.tax.save(update_fields=["rate_bps"])
        self.assertTrue(inspect_commerce()["consistent"])
        invoice = self.client.get(f"/api/v1/commerce/orders/{order.pk}/invoice/")
        self.assertContains(invoice, self.tax.label)
        self.assertEqual(invoice.context["deliveries"][0].total_toman, order.grand_total_toman)

    def test_policy_change_requires_reapproval_and_replay_preserves_accepted_terms(self):
        quote = self.preview()
        self.tax.rate_bps = 2000
        self.tax.save(update_fields=["rate_bps"])
        self.assertEqual(self.checkout(quote).json()["error"], "quote_changed")
        self.assertFalse(Order.objects.exists())
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.reserved_quantity, 0)
        self.assertTrue(CartLine.objects.filter(cart=self.cart).exists())
        fresh = self.preview()
        key = uuid4()
        first = self.checkout(fresh, key)
        self.tax.is_active = False
        self.tax.save(update_fields=["is_active"])
        replay = self.checkout(fresh, key)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.json()["order"]["tax_total_toman"], replay.json()["order"]["tax_total_toman"])

    def test_zero_default_and_no_parent_inheritance(self):
        self.tax.delete()
        parent = Category.objects.create(name="Parent", slug="taxparent")
        TaxRule.objects.create(category=parent, label="Parent tax", rate_bps=1000, is_active=True)
        self.category.parent = parent
        self.category.save(update_fields=["parent"])
        quote = self.preview()
        self.assertEqual(quote["tax_total_toman"], 0)
        self.assertEqual(self.checkout(quote).json()["order"]["grand_total_toman"], 21500)

    def test_multi_seller_and_category_allocation(self):
        category = Category.objects.create(name="Other", slug="othertax")
        product = Product.objects.create(category=category, title="Other product", slug="othertaxproduct", status="published")
        variant = Variant.objects.create(product=product, sku="other-tax-sku")
        seller = Seller.objects.create(name="Second tax seller", status="approved")
        offer = Offer.objects.create(variant=variant, seller=seller, price_toman=10003, available_quantity=5, status="active")
        CartLine.objects.create(cart=self.cart, offer=offer, quantity=1)
        TaxRule.objects.create(category=category, label="Second configured tax", rate_bps=2345, is_active=True)
        response = self.checkout()
        order = Order.objects.get()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(order.tax_total_toman, 20000*1234//10000 + 10003*2345//10000)
        self.assertEqual(order.grand_total_toman, 30003+3000+order.tax_total_toman)
        self.assertTrue(inspect_commerce()["consistent"])

    def test_unit_refunds_preserve_tax_and_exclude_it_from_seller_payable(self):
        self.offer.price_toman = 10003
        self.offer.save(update_fields=["price_toman"])
        self.line.quantity = 3
        self.line.save(update_fields=["quantity"])
        self.offer.seller.commission_bps = 1500
        self.offer.seller.save(update_fields=["commission_bps"])
        self.pay()
        self.delivery.status = "delivered"
        self.delivery.save(update_fields=["status"])
        accrue_delivery(self.delivery.pk)
        expected = self.order_line.line_total_toman - self.order_line.line_total_toman*1500//10000 + 1500
        self.assertEqual(LedgerEntry.objects.filter(kind="seller_payable").aggregate(total=Sum("amount_toman"))["total"], expected)
        self.tax.rate_bps = 0
        self.tax.save(update_fields=["rate_bps"])
        total, tax_total = 0, 0
        for _ in range(3):
            case = create_line_return(self.user, self.delivery.pk, self.order_line.pk, 1, "Test unit return")
            total += case.requested_amount_toman
            tax_total += case.lines.get().tax_amount_toman
            transition_return(case.pk, "approved")
            transition_return(case.pk, "received")
            refund_sandbox_return(case.pk)
            refund_sandbox_return(case.pk)
        self.assertEqual(tax_total, self.order_line.tax_toman)
        self.assertEqual(total, self.order_line.line_total_toman+self.order_line.tax_toman)
        self.assertEqual(LedgerEntry.objects.filter(kind="payment_refund").count(), 3)
        self.assertEqual(LedgerEntry.objects.filter(kind="seller_payable").aggregate(total=Sum("amount_toman"))["total"], 1500)
        report = seller_performance(self.delivery.seller_id)
        self.assertEqual(report["refunded_item_total_toman"], self.order_line.line_total_toman)
        self.assertEqual(report["refunded_tax_toman"], self.order_line.tax_toman)
        self.assertTrue(inspect_commerce()["consistent"])

    def test_paid_cancellation_refunds_tax_and_shipping_separately(self):
        self.pay()
        case = request_cancellation(self.user, self.delivery.pk, "Cancel before shipment")
        self.assertEqual(case.amount_toman, self.order.grand_total_toman)
        review_cancellation(case.pk, "approved", self.admin, "Approved cancellation")
        refund_sandbox_cancellation(case.pk)
        refund_sandbox_cancellation(case.pk)
        self.assertEqual(LedgerEntry.objects.get(kind="payment_refund").amount_toman, -self.order.grand_total_toman)
        report = seller_performance(self.delivery.seller_id)
        self.assertEqual(report["cancelled_shipping_refund_toman"], 1500)
        self.assertEqual(report["refunded_tax_toman"], self.order.tax_total_toman)
        self.assertTrue(inspect_commerce()["consistent"])

    def test_admin_authorization_validation_csrf_and_audit_rollback(self):
        payload = {"label": "New tax", "rate_bps": 2000, "is_active": True, "reason": "Configured test change"}
        self.assertEqual(self.client.put(self.path, json.dumps(payload), content_type="application/json").status_code, 403)
        self.client.force_login(self.admin)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.put(self.path, json.dumps(payload), content_type="application/json").status_code, 403)
        for value in [True, -1, 10001, "100", 1.5]:
            self.assertEqual(self.client.put(self.path, json.dumps({**payload, "rate_bps": value}), content_type="application/json").status_code, 400)
        with patch("operations.tax_api._audit", side_effect=RuntimeError("Audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.put(self.path, json.dumps(payload), content_type="application/json")
        self.tax.refresh_from_db()
        self.assertEqual(self.tax.rate_bps, 1234)
        self.assertEqual(self.client.put(self.path, json.dumps(payload), content_type="application/json").status_code, 200)
        event = AuditEvent.objects.get(action="tax_rule_saved")
        self.assertEqual(event.before["rate_bps"], 1234)
        self.assertEqual(event.after["rate_bps"], 2000)

    def test_checker_detects_tax_snapshot_corruption(self):
        self.checkout()
        OrderLine.objects.update(tax_toman=1)
        codes = {row["code"] for row in inspect_commerce()["issues"]}
        self.assertIn("order_line_tax_mismatch", codes)
        self.assertIn("order_snapshot_total_mismatch", codes)

    def test_checker_detects_refund_tax_component_corruption(self):
        self.pay()
        self.delivery.status = "delivered"
        self.delivery.save(update_fields=["status"])
        case = create_line_return(self.user, self.delivery.pk, self.order_line.pk, 1, "Component verification")
        ReturnLine.objects.filter(case=case).update(tax_amount_toman=0)
        self.assertIn("return_component_mismatch", {row["code"] for row in inspect_commerce()["issues"]})

    def test_changed_product_category_requires_reapproval(self):
        quote = self.preview()
        category = Category.objects.create(name="Untaxed category", slug="untaxed-reassigned")
        Product.objects.filter(pk=self.offer.variant.product_id).update(category=category)
        self.assertEqual(self.checkout(quote).json()["error"], "quote_changed")
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.preview()["tax_total_toman"], 0)
