import json
from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from accounts.closure import blockers, request_closure, decide_closure, ClosureError
from payments import test_marketplace_flow as flow_fixtures
from payments.orchestration import PaymentError
from payments.settlements import prepare_settlement, approve_settlement, simulate_payout
from sellers.models import Seller, SellerMembership
from .disputes import open_dispute, seller_respond, review_dispute, DisputeError
from .models import OrderDispute, OutboxEvent


@override_settings(DEBUG=True, ENABLE_SANDBOX_PAYMENTS=True)
class DisputeTests(TestCase):
    def setUp(self):
        flow_fixtures.MarketplaceFlowTests.setUp(self)
        flow_fixtures.MarketplaceFlowTests.pay_and_deliver(self)
        self.owner = get_user_model().objects.create_user("09123456401")
        SellerMembership.objects.create(user=self.owner, seller=self.delivery.seller, role="owner")
        self.creator.groups.add(Group.objects.create(name="marketplace_manager"))

    def test_creation_is_owned_idempotent_and_does_not_refund_money(self):
        case = open_dispute(self.buyer, self.delivery.pk, "Received wrong product")
        self.assertEqual(open_dispute(self.buyer, self.delivery.pk, case.reason).pk, case.pk)
        self.assertEqual(OrderDispute.objects.count(), 1)
        self.assertEqual(OutboxEvent.objects.filter(topic="dispute.updated").count(), 1)
        from payments.models import LedgerEntry
        self.assertFalse(LedgerEntry.objects.filter(kind="payment_refund").exists())
        with self.assertRaises(DisputeError):
            open_dispute(self.owner, self.delivery.pk, "Someone else's order")
        with self.assertRaises(DisputeError):
            open_dispute(self.buyer, self.delivery.pk, "Different request")

    def test_seller_response_escalation_and_resolution_are_validated(self):
        case = open_dispute(self.buyer, self.delivery.pk, "Wrong product")
        with self.assertRaises(DisputeError):
            seller_respond(self.buyer, case.pk, self.delivery.seller_id, "Response")
        seller_respond(self.owner, case.pk, self.delivery.seller_id, "Replacement offered")
        with self.assertRaises(DisputeError):
            seller_respond(self.owner, case.pk, self.delivery.seller_id, "Repeated response")
        review_dispute(self.creator, case.pk, "escalated", "Requires review", internal_note="Private seller risk note")
        review_dispute(self.creator, case.pk, "resolved", "Reviewed evidence", resolution="Replacement accepted")
        with self.assertRaises(DisputeError):
            review_dispute(self.creator, case.pk, "rejected", "Changed decision", resolution="Changed result")

    def test_open_dispute_holds_preparation_and_prepared_payout(self):
        case = open_dispute(self.buyer, self.delivery.pk, "Wrong product")
        with self.assertRaises(PaymentError):
            prepare_settlement(self.creator, self.delivery.seller_id, uuid4())
        review_dispute(self.creator, case.pk, "resolved", "Reviewed evidence", resolution="Issue resolved")
        settlement = prepare_settlement(self.creator, self.delivery.seller_id, uuid4())
        approve_settlement(self.approver, settlement.pk)
        # An already reviewed case cannot be reopened by the customer.
        self.assertEqual(open_dispute(self.buyer, self.delivery.pk, case.reason).status, "resolved")
        simulate_payout(settlement.pk)

    def test_dispute_after_preparation_blocks_payout_until_resolution(self):
        settlement = prepare_settlement(self.creator, self.delivery.seller_id, uuid4())
        approve_settlement(self.approver, settlement.pk)
        case = open_dispute(self.buyer, self.delivery.pk, "Wrong product")
        with self.assertRaises(PaymentError) as caught:
            simulate_payout(settlement.pk)
        self.assertEqual(caught.exception.code, "settlement_has_open_disputes")
        settlement.refresh_from_db()
        self.assertEqual(settlement.status, "approved")
        review_dispute(self.creator, case.pk, "rejected", "Reviewed evidence", resolution="No discrepancy found")
        simulate_payout(settlement.pk)

    def test_internal_notes_and_customer_records_are_private(self):
        case = open_dispute(self.buyer, self.delivery.pk, "Wrong product")
        review_dispute(self.creator, case.pk, "escalated", "Reviewed evidence", internal_note="INTERNAL-PRIVATE")
        for user, path in [(self.buyer, "/api/v1/operations/my-disputes/"), (self.owner, f"/api/v1/seller/stores/{self.delivery.seller_id}/disputes/")]:
            self.client.force_login(user)
            result = self.client.get(path)
            self.assertEqual(result.status_code, 200)
            self.assertNotIn("INTERNAL-PRIVATE", result.content.decode())
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/api/v1/operations/my-disputes/").json()["disputes"], [])
        self.client.force_login(self.buyer)
        exported = self.client.get("/api/v1/auth/export/")
        self.assertNotIn("INTERNAL-PRIVATE", exported.content.decode())
        self.assertIn("open_dispute", blockers(self.buyer))
        closure = request_closure(self.buyer, "Close account")
        with self.assertRaises(ClosureError):
            decide_closure(closure.pk, "completed", self.creator, "Verified request")

    def test_roles_csrf_and_failed_audit_rollback(self):
        case = open_dispute(self.buyer, self.delivery.pk, "Wrong product")
        path = f"/api/v1/operations/disputes/{case.pk}/decision/"
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(path, "{}", content_type="application/json").status_code, 403)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.creator)
        self.assertEqual(csrf.post(path, "{}", content_type="application/json").status_code, 403)
        with patch("operations.disputes.record", side_effect=RuntimeError("Audit failed")):
            with self.assertRaises(RuntimeError):
                review_dispute(self.creator, case.pk, "resolved", "Evidence reviewed", resolution="Resolved")
        case.refresh_from_db()
        self.assertEqual(case.status, "open")
