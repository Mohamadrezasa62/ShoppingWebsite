from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from payments import test_marketplace_flow as fixtures
from payments.settlements import prepare_settlement, approve_settlement, simulate_payout
from payments.orchestration import PaymentError
from .disputes import open_dispute
from .models import OrderDispute, Notification, CampaignRecipient
from .campaigns import campaign_action, set_preference
from .events import process_event
from . import test_campaigns as marketing_fixtures
from . import risk_api
from catalog import test_trust as trust_fixtures
from commerce.fulfillment import transition_delivery, FulfillmentError
from commerce.models import OrderDelivery
from django.contrib.auth.models import Group
from django.test import RequestFactory
import json


@skipUnless(connection.vendor == "postgresql", "Dispute/payout row locking requires PostgreSQL")
@override_settings(DEBUG=True, ENABLE_SANDBOX_PAYMENTS=True)
class DisputePayoutConcurrencyTests(TransactionTestCase):
    def setUp(self):
        fixtures.MarketplaceFlowTests.setUp(self)
        fixtures.MarketplaceFlowTests.pay_and_deliver(self)
        self.settlement = prepare_settlement(self.creator, self.delivery.seller_id, uuid4())
        approve_settlement(self.approver, self.settlement.pk)

    def test_payout_cannot_pass_an_earlier_open_dispute(self):
        gate = Barrier(2)
        def action(kind):
            connections.close_all()
            try:
                gate.wait(timeout=10)
                if kind == "dispute":
                    buyer = get_user_model().objects.get(pk=self.buyer.pk)
                    return open_dispute(buyer, self.delivery.pk, "Wrong product").pk
                try:
                    return simulate_payout(self.settlement.pk).status
                except PaymentError as exc:
                    return exc.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            dispute_id, result = list(executor.map(action, ["dispute", "payout"]))
        case = OrderDispute.objects.get(pk=dispute_id)
        self.settlement.refresh_from_db()
        if result == "simulated_paid":
            # A later dispute cannot undo a payment already committed.
            self.assertLessEqual(self.settlement.paid_at, case.created_at)
        else:
            self.assertEqual(result, "settlement_has_open_disputes")
            self.assertEqual(self.settlement.status, "approved")


@skipUnless(connection.vendor == "postgresql", "Outbox row locking requires PostgreSQL")
class CampaignEventConcurrencyTests(TransactionTestCase):
    def setUp(self):
        marketing_fixtures.MarketingTests.setUp(self)
        set_preference(self.user, True)
        campaign = marketing_fixtures.MarketingTests.campaign(self)
        self.event = marketing_fixtures.MarketingTests.queue(self, campaign)

    def test_same_campaign_event_delivers_once(self):
        gate = Barrier(2)
        def dispatch(_):
            connections.close_all()
            try:
                gate.wait(timeout=10)
                return process_event(self.event.pk)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(dispatch, range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(CampaignRecipient.objects.get().status, "delivered")


@skipUnless(connection.vendor == "postgresql", "Risk/fulfillment row locking requires PostgreSQL")
class RiskShippingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        trust_fixtures.TrustTests.setUp(self)
        self.order.status = "paid"
        self.order.save(update_fields=["status"])
        self.delivery.status = "packing"
        self.delivery.save(update_fields=["status"])
        self.manager = get_user_model().objects.create_user("09123456599", is_staff=True)
        self.manager.groups.add(Group.objects.get_or_create(name="marketplace_manager")[0])

    def test_shipping_cannot_pass_a_committed_operational_hold(self):
        gate = Barrier(2)
        payload = {"order_id": self.order.pk, "request_key": str(uuid4()), "category": "other", "severity": "high", "description": "Review shipment", "hold_fulfillment": True, "reason": "Manual review needed"}
        def action(kind):
            connections.close_all()
            try:
                if kind == "hold":
                    actor = get_user_model().objects.get(pk=self.manager.pk)
                    request = RequestFactory().post("/api/v1/operations/risk-cases/create/", json.dumps(payload), content_type="application/json")
                    request.user = actor
                    request._dont_enforce_csrf_checks = True
                    gate.wait(timeout=10)
                    return risk_api.create(request).status_code
                gate.wait(timeout=10)
                try:
                    return transition_delivery(self.delivery.pk, "shipped", "RACE-TRACK").status
                except FulfillmentError:
                    return "held"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            hold_result, shipping_result = list(executor.map(action, ["hold", "ship"]))
        delivery = OrderDelivery.objects.get(pk=self.delivery.pk)
        if hold_result == 201:
            self.assertEqual(shipping_result, "held")
            self.assertEqual(delivery.status, "packing")
        else:
            self.assertEqual(hold_result, 409)
            self.assertEqual(shipping_result, "shipped")
            self.assertEqual(delivery.status, "shipped")
