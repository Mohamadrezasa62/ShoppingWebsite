from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from catalog.models import Offer
from sellers.models import Seller
from payments import tests as payment_fixtures
from payments.models import LedgerEntry
from payments.orchestration import initiate_sandbox, simulate_result
from .models import DeliveryCancellation, OrderDelivery, OrderLine
from .cancellations import request_cancellation, review_cancellation, refund_sandbox_cancellation
from .fulfillment import FulfillmentError, transition_delivery
from .services import CheckoutError


@override_settings(DEBUG=True, ENABLE_SANDBOX_PAYMENTS=True)
class CancellationTests(TestCase):
    def setUp(self):
        payment_fixtures.PaymentCaptureTests.setUp(self)
        self.buyer = self.order.user
        self.delivery = self.order.deliveries.get()
        self.actor = get_user_model().objects.create_user("09123456873", is_staff=True)
        self.other = get_user_model().objects.create_user("09123456874")
        seller = Seller.objects.create(name="Second seller")
        self.second_offer = Offer.objects.create(variant=self.offer.variant, seller=seller, price_toman=500, available_quantity=3, reserved_quantity=1)
        self.second = OrderDelivery.objects.create(order=self.order, seller=seller, seller_name=seller.name, fulfillment="seller", shipping_fee_toman=200, min_days=1, max_days=2)
        OrderLine.objects.create(delivery=self.second, offer=self.second_offer, product_title="Phone", variant_attributes={}, seller_name=seller.name, quantity=1, unit_price_toman=500, line_total_toman=500)
        OrderLine.objects.filter(delivery=self.delivery).update(discount_toman=1000)
        self.order.item_total_toman += 500
        self.order.shipping_total_toman += 200
        self.order.discount_total_toman = 1000
        self.order.grand_total_toman += 700 - 1000
        self.order.save()
        attempt = initiate_sandbox(self.buyer, self.order.pk, uuid4())
        simulate_result(self.buyer, attempt.pk, "success")

    def approve(self):
        case = request_cancellation(self.buyer, self.delivery.pk, "Changed purchase decision")
        review_cancellation(case.pk, "approved", self.actor, "Cancellation reviewed")
        return case

    def test_partial_order_cancellation_refunds_and_restores_only_one_delivery_once(self):
        case = self.approve()
        self.assertEqual(case.amount_toman, 24000)
        refund_sandbox_cancellation(case.pk)
        refund_sandbox_cancellation(case.pk)
        self.offer.refresh_from_db()
        self.second_offer.refresh_from_db()
        self.delivery.refresh_from_db()
        self.second.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.offer.available_quantity, 5)
        self.assertEqual(self.second_offer.available_quantity, 2)
        self.assertEqual(self.delivery.status, "cancelled")
        self.assertEqual(self.second.status, "awaiting_fulfillment")
        self.assertEqual(self.order.status, "paid")
        refunds = LedgerEntry.objects.filter(kind="payment_refund")
        self.assertEqual(refunds.count(), 1)
        self.assertEqual(refunds.get().amount_toman, -24000)
        self.assertFalse(LedgerEntry.objects.filter(kind="seller_payable").exists())
        from sellers.reports import seller_performance
        report = seller_performance(self.delivery.seller_id)
        self.assertEqual(report["cancelled_units"], 2)
        self.assertEqual(report["refunded_item_total_toman"], 19000)
        self.assertEqual(report["cancelled_shipping_refund_toman"], 5000)
        self.assertEqual(seller_performance(self.second.seller_id)["refunded_units"], 0)

    def test_pending_request_holds_fulfillment_and_rejection_releases_hold(self):
        case = request_cancellation(self.buyer, self.delivery.pk, "Changed purchase decision")
        self.assertEqual(request_cancellation(self.buyer, self.delivery.pk, case.reason).pk, case.pk)
        with self.assertRaises(CheckoutError):
            request_cancellation(self.buyer, self.delivery.pk, "Different request")
        with self.assertRaises(FulfillmentError):
            transition_delivery(self.delivery.pk, "packing")
        review_cancellation(case.pk, "rejected", self.actor, "Request rejected")
        transition_delivery(self.delivery.pk, "packing")
        self.assertFalse(LedgerEntry.objects.filter(kind="payment_refund").exists())

    def test_shipped_delivery_and_other_customer_are_ineligible(self):
        with self.assertRaises(CheckoutError) as caught:
            request_cancellation(self.other, self.delivery.pk, "Cancel someone else")
        self.assertEqual(caught.exception.status, 404)
        transition_delivery(self.delivery.pk, "packing")
        transition_delivery(self.delivery.pk, "shipped", "TRACK-1")
        with self.assertRaises(CheckoutError):
            request_cancellation(self.buyer, self.delivery.pk, "Too late to cancel")
        self.assertFalse(DeliveryCancellation.objects.exists())

    def test_refund_failure_rolls_back_inventory_and_case_status(self):
        case = self.approve()
        with patch("commerce.cancellations.record_verified_refund", side_effect=ValueError("Provider failure")):
            with self.assertRaises(ValueError):
                refund_sandbox_cancellation(case.pk)
        case.refresh_from_db()
        self.offer.refresh_from_db()
        self.assertEqual(case.status, "approved")
        self.assertEqual(self.offer.available_quantity, 3)
        self.assertFalse(LedgerEntry.objects.filter(kind="payment_refund").exists())

    def test_production_never_simulates_refund(self):
        case = self.approve()
        with override_settings(DEBUG=False):
            with self.assertRaises(CheckoutError) as caught:
                refund_sandbox_cancellation(case.pk)
        self.assertEqual(caught.exception.status, 503)
        self.assertFalse(LedgerEntry.objects.filter(kind="payment_refund").exists())

    def test_customer_list_is_private_and_finance_cannot_approve(self):
        import json
        from django.contrib.auth.models import Group
        case = request_cancellation(self.buyer, self.delivery.pk, "Changed purchase decision")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/v1/commerce/cancellations/").json()["cancellations"], [])
        self.actor.groups.add(Group.objects.create(name="finance_operator"))
        self.client.force_login(self.actor)
        result = self.client.post(f"/api/v1/operations/cancellations/{case.pk}/decision/", json.dumps({"status": "approved", "reason": "Reviewed"}), content_type="application/json")
        self.assertEqual(result.status_code, 403)
