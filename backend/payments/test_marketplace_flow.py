import json
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from commerce.models import OrderLine
from commerce.returns import create_line_return, refund_sandbox_return, transition_return
from commerce.services import CheckoutError
from .models import LedgerEntry, Settlement
from .orchestration import PaymentError, initiate_sandbox, simulate_result
from .settlements import approve_settlement, cancel_settlement, prepare_settlement, simulate_payout
from .tests import PaymentCaptureTests


@override_settings(DEBUG=True, ENABLE_SANDBOX_PAYMENTS=True)
class MarketplaceFlowTests(TestCase):
    def setUp(self):
        PaymentCaptureTests.setUp(self)
        self.buyer = self.order.user
        self.delivery = self.order.deliveries.get()
        self.line = self.delivery.lines.get()
        OrderLine.objects.filter(pk=self.line.pk).update(commission_bps=1500)
        self.line.refresh_from_db()
        self.creator = get_user_model().objects.create_user("09123456201", is_staff=True)
        self.approver = get_user_model().objects.create_user("09123456202", is_staff=True)

    def pay_and_deliver(self):
        attempt = initiate_sandbox(self.buyer, self.order.pk, uuid4())
        simulate_result(self.buyer, attempt.pk, "success")
        self.delivery.status = "delivered"
        self.delivery.save(update_fields=["status"])
        return attempt

    def test_payment_idempotency_ownership_and_real_provider_disabled(self):
        key = uuid4()
        first = initiate_sandbox(self.buyer, self.order.pk, key)
        self.assertEqual(first.pk, initiate_sandbox(self.buyer, self.order.pk, key).pk)
        simulate_result(self.buyer, first.pk, "success")
        simulate_result(self.buyer, first.pk, "success")
        self.assertEqual(LedgerEntry.objects.filter(kind="payment_capture").count(), 1)
        with self.assertRaises(PaymentError):
            simulate_result(self.creator, first.pk, "success")
        self.client.force_login(self.buyer)
        response = self.client.post("/api/v1/payments/initiate/", json.dumps({"order_id": self.order.pk, "provider": "card_gateway", "idempotency_key": str(uuid4())}), content_type="application/json")
        self.assertEqual(response.status_code, 503)

    @override_settings(DEBUG=False)
    def test_simulation_cannot_operate_in_production(self):
        with self.assertRaises(PaymentError):
            initiate_sandbox(self.buyer, self.order.pk, uuid4())
        self.assertEqual(self.client.get("/api/v1/payments/methods/").json()["available"], [])

    def test_partial_return_refund_and_settlement_do_not_duplicate_money(self):
        self.pay_and_deliver()
        case = create_line_return(self.buyer, self.delivery.pk, self.line.pk, 1, "Damaged item")
        with self.assertRaises(CheckoutError):
            create_line_return(self.buyer, self.delivery.pk, self.line.pk, 2, "Duplicate quantity")
        transition_return(case.pk, "approved")
        transition_return(case.pk, "received", restock=False)
        refund_sandbox_return(case.pk)
        refund_sandbox_return(case.pk)
        self.assertEqual(LedgerEntry.objects.filter(kind="payment_refund").count(), 1)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.available_quantity, 3)
        key = uuid4()
        settlement = prepare_settlement(self.creator, self.delivery.seller_id, key)
        self.assertEqual(settlement.amount_toman, 13500)
        self.assertEqual(settlement.pk, prepare_settlement(self.creator, self.delivery.seller_id, key).pk)
        with self.assertRaises(PaymentError):
            approve_settlement(self.creator, settlement.pk)
        approve_settlement(self.approver, settlement.pk)
        simulate_payout(settlement.pk)
        simulate_payout(settlement.pk)
        self.assertEqual(Settlement.objects.count(), 1)
        self.assertEqual(Settlement.objects.get().status, "simulated_paid")

    def test_refund_after_preparation_requires_recalculation(self):
        self.pay_and_deliver()
        settlement = prepare_settlement(self.creator, self.delivery.seller_id, uuid4())
        approve_settlement(self.approver, settlement.pk)
        case = create_line_return(self.buyer, self.delivery.pk, self.line.pk, 1, "Damaged item")
        with self.assertRaises(PaymentError):
            simulate_payout(settlement.pk)
        transition_return(case.pk, "approved")
        transition_return(case.pk, "received")
        refund_sandbox_return(case.pk)
        with self.assertRaises(PaymentError):
            simulate_payout(settlement.pk)
        cancel_settlement(settlement.pk)
        self.assertEqual(prepare_settlement(self.creator, self.delivery.seller_id, uuid4()).amount_toman, 13500)

    def test_restock_requires_inspection_and_happens_once(self):
        self.pay_and_deliver()
        case = create_line_return(self.buyer, self.delivery.pk, self.line.pk, 1, "Wrong size")
        transition_return(case.pk, "approved")
        transition_return(case.pk, "received", restock=True)
        with self.assertRaises(CheckoutError):
            transition_return(case.pk, "received", restock=True)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.available_quantity, 4)
