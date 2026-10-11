import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from .models import Notification


class SupportContentTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user("09123456001")
        self.other = get_user_model().objects.create_user("09123456002")
        self.staff = get_user_model().objects.create_user("09123456003", is_staff=True)
        self.staff.groups.add(Group.objects.create(name="support_agent"))
        self.catalog = get_user_model().objects.create_user("09123456004", is_staff=True)
        self.catalog.groups.add(Group.objects.create(name="catalog_operator"))

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def test_tickets_are_private_and_internal_notes_do_not_leak(self):
        self.client.force_login(self.buyer)
        result = self.post("/api/v1/operations/my-tickets/", {"subject": "Delivery question", "body": "Where is my parcel?"})
        self.assertEqual(result.status_code, 201)
        ticket_id = result.json()["ticket"]["id"]
        self.client.force_login(self.other)
        self.assertEqual(self.post(f"/api/v1/operations/my-tickets/{ticket_id}/reply/", {"body": "attack"}).status_code, 404)
        self.client.force_login(self.staff)
        path = f"/api/v1/operations/tickets/{ticket_id}/reply/"
        self.assertEqual(self.post(path, {"body": "Internal risk assessment", "is_internal": True, "status": "open", "reason": "Investigation"}).status_code, 200)
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(self.post(path, {"body": "Carrier contacted", "status": "awaiting_customer", "reason": "Customer update"}).status_code, 200)
        self.client.force_login(self.buyer)
        messages = self.client.get("/api/v1/operations/my-tickets/").json()["tickets"][0]["messages"]
        self.assertEqual(len(messages), 2)
        self.assertFalse(any(message["is_internal"] for message in messages))
        notification_id = Notification.objects.get().pk
        self.client.force_login(self.other)
        self.assertEqual(self.post(f"/api/v1/operations/notifications/{notification_id}/read/", {}).status_code, 404)

    def test_draft_content_not_public_and_publishing_is_authorized(self):
        self.client.force_login(self.catalog)
        result = self.post("/api/v1/operations/pages/", {"title": "Return policy", "slug": "returns", "body": "Development policy", "kind": "policy", "reason": "Draft policy"})
        self.assertEqual(result.status_code, 201)
        page_id = result.json()["page"]["id"]
        self.assertEqual(self.client.get("/api/v1/operations/content/returns/").status_code, 404)
        response = self.client.patch(f"/api/v1/operations/pages/{page_id}/", json.dumps({"is_published": True, "version": result.json()["page"]["version"], "reason": "Policy approved"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/operations/content/returns/").status_code, 200)
        self.client.force_login(self.buyer)
        self.assertEqual(self.post("/api/v1/operations/pages/", {"reason": "Unauthorized"}).status_code, 403)
