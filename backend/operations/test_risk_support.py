import json
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from catalog import test_trust
from commerce.fulfillment import transition_delivery, FulfillmentError
from .models import AuditEvent, OrderRiskCase, SupportTicket


class RiskSupportTests(TestCase):
    def setUp(self):
        test_trust.TrustTests.setUp(self)
        self.order.status = "paid"
        self.order.save(update_fields=["status"])
        self.manager = get_user_model().objects.create_user("09123456501", is_staff=True)
        self.manager.groups.add(Group.objects.get_or_create(name="marketplace_manager")[0])
        self.support = get_user_model().objects.create_user("09123456502", is_staff=True)
        self.support.groups.add(Group.objects.get_or_create(name="support_agent")[0])
        self.finance = get_user_model().objects.create_user("09123456503", is_staff=True)
        self.finance.groups.add(Group.objects.get_or_create(name="finance_operator")[0])
        self.client.force_login(self.manager)
        self.payload = {"order_id": self.order.pk, "request_key": str(uuid4()), "category": "payment_abuse", "severity": "high", "description": "INTERNAL risk context", "hold_fulfillment": True, "reason": "Investigate report"}
        self.ticket = SupportTicket.objects.create(user=self.buyer, order=self.order, subject="Delivery help")

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def create(self, **change):
        return self.post("/api/v1/operations/risk-cases/create/", {**self.payload, **change})

    def decide(self, pk, action="clear", outcome="dismissed"):
        return self.post(f"/api/v1/operations/risk-cases/{pk}/decision/", {"action": action, "outcome": outcome, "resolution": "Evidence reviewed", "reason": "Review finished"})

    def route(self, **change):
        return self.post(f"/api/v1/operations/tickets/{self.ticket.pk}/route/", {"assigned_to": self.manager.pk, "priority": "urgent", "is_escalated": True, "reason": "Needs manager review", **change})

    def test_hold_escalation_resolution_and_multiple_cases(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create().status_code, 200)
        self.assertEqual(self.create(severity="low").status_code, 409)
        first = OrderRiskCase.objects.get()
        with self.assertRaises(FulfillmentError):
            transition_delivery(self.delivery.pk, "packing")
        self.assertEqual(self.decide(first.pk, "escalate", "").status_code, 200)
        self.assertEqual(self.create(request_key=str(uuid4())).status_code, 201)
        second = OrderRiskCase.objects.exclude(pk=first.pk).get()
        self.assertEqual(self.decide(first.pk).status_code, 200)
        with self.assertRaises(FulfillmentError):
            transition_delivery(self.delivery.pk, "packing")
        self.assertEqual(self.decide(second.pk, outcome="confirmed").status_code, 200)
        self.assertEqual(transition_delivery(self.delivery.pk, "packing").status, "packing")
        self.assertEqual(self.decide(first.pk).status_code, 409)
        self.assertTrue(AuditEvent.objects.filter(action="risk_case_reviewed").exists())

    def test_hold_cannot_stop_already_shipped_delivery(self):
        transition_delivery(self.delivery.pk, "packing")
        transition_delivery(self.delivery.pk, "shipped", "TRACK-1")
        self.assertEqual(self.create().status_code, 409)
        self.assertEqual(self.create(hold_fulfillment=False).status_code, 201)
        self.assertEqual(transition_delivery(self.delivery.pk, "delivered").status, "delivered")
        self.order.status = "cancelled"
        self.order.save(update_fields=["status"])
        self.assertEqual(self.create(request_key=str(uuid4()), hold_fulfillment=False).status_code, 409)

    def test_risk_permissions_privacy_validation_and_atomic_audit(self):
        self.client.force_login(self.support)
        self.assertEqual(self.create().status_code, 403)
        self.assertEqual(self.client.get("/api/v1/operations/risk-cases/").status_code, 200)
        self.client.force_login(self.manager)
        with patch("operations.risk_api._audit", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.create()
        self.assertFalse(OrderRiskCase.objects.exists())
        for change in ({"severity": "extreme"}, {"hold_fulfillment": "yes"}, {"description": "x\x00y"}, {"order_id": True}, {"request_key": "bad"}, {"status": "cleared"}):
            self.assertEqual(self.create(**change).status_code, 400)
        self.create()
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get("/api/v1/operations/risk-cases/").status_code, 403)
        self.assertNotIn("INTERNAL risk context", self.client.get("/api/v1/auth/export/").content.decode())
        self.assertNotIn("INTERNAL risk context", self.client.get(f"/api/v1/commerce/orders/{self.order.pk}/").content.decode())

    def test_route_requires_eligible_assignee_and_manager_resolution(self):
        self.client.force_login(self.support)
        self.assertEqual(self.route(assigned_to=self.support.pk).status_code, 400)
        self.assertEqual(self.route(assigned_to=self.finance.pk).status_code, 404)
        self.assertEqual(self.route().status_code, 200)
        self.assertEqual(self.route(is_escalated=False, assigned_to=self.support.pk).status_code, 403)
        reply = {"body": "Please review", "status": "closed", "reason": "Work completed", "is_internal": False}
        path = f"/api/v1/operations/tickets/{self.ticket.pk}/reply/"
        self.assertEqual(self.post(path, reply).status_code, 409)
        reply["status"] = "awaiting_customer"
        self.assertEqual(self.post(path, reply).status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_to_id, self.manager.pk)
        self.client.force_login(self.manager)
        self.assertEqual(self.route(is_escalated=False, assigned_to=self.support.pk).status_code, 200)
        reply["status"] = "closed"
        self.assertEqual(self.post(path, reply).status_code, 200)
        self.assertEqual(self.route().status_code, 409)

    def test_queue_priority_and_private_routing_metadata(self):
        urgent = SupportTicket.objects.create(user=self.buyer, subject="Urgent", priority="urgent")
        escalated = SupportTicket.objects.create(user=self.buyer, subject="Escalated", is_escalated=True, assigned_to=self.manager)
        rows = self.client.get("/api/v1/operations/tickets/").json()["tickets"]
        self.assertEqual([row["id"] for row in rows[:2]], [escalated.pk, urgent.pk])
        assignees = self.client.get("/api/v1/operations/support-assignees/").json()["assignees"]
        self.assertEqual({row["id"] for row in assignees}, {self.manager.pk, self.support.pk})
        self.assertTrue(all(set(row) == {"id", "name"} for row in assignees))
        self.client.force_login(self.buyer)
        public = self.client.get("/api/v1/operations/my-tickets/").json()["tickets"]
        self.assertTrue(all("priority" not in row and "is_escalated" not in row and row["assigned_to"] is None for row in public))
        self.assertEqual(self.route().status_code, 403)

    def test_route_rollback_and_csrf(self):
        with patch("operations.support_api._audit", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.route()
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.is_escalated)
        self.assertEqual(self.ticket.priority, "normal")
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.manager)
        self.assertEqual(csrf.post("/api/v1/operations/risk-cases/create/", json.dumps(self.payload), content_type="application/json").status_code, 403)
        self.assertEqual(csrf.post(f"/api/v1/operations/tickets/{self.ticket.pk}/route/", json.dumps({}), content_type="application/json").status_code, 403)
