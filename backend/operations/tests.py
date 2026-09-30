import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from catalog.models import Category
from sellers.models import Seller

from .models import AuditEvent


class AdminOperationTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user("09123456780", is_staff=True)
        self.catalog_user = get_user_model().objects.create_user("09123456781", is_staff=True)
        self.system_user = get_user_model().objects.create_user("09123456782", is_staff=True)
        self.buyer = get_user_model().objects.create_user("09123456783")
        self.manager.groups.add(Group.objects.create(name="marketplace_manager"))
        self.catalog_user.groups.add(Group.objects.create(name="catalog_operator"))
        self.system_user.groups.add(Group.objects.create(name="system_administrator"))
        self.finance_group = Group.objects.create(name="finance_operator")

    def post_json(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def test_seller_decision_requires_role_and_audits_transition(self):
        seller = Seller.objects.create(name="New store")
        url = f"/api/v1/operations/sellers/{seller.pk}/decision/"
        self.client.force_login(self.catalog_user)
        self.assertEqual(self.post_json(url, {"status": "approved", "reason": "Documents verified"}).status_code, 403)
        self.client.force_login(self.manager)
        self.assertEqual(self.post_json(url, {"status": "approved", "reason": "Documents verified"}).status_code, 200)
        seller.refresh_from_db()
        self.assertEqual(seller.status, Seller.Status.APPROVED)
        event = AuditEvent.objects.get(action="seller_decision")
        self.assertEqual(event.actor, self.manager)
        self.assertEqual(event.before["status"], "applied")
        self.assertEqual(event.after["status"], "approved")
        self.assertEqual(self.post_json(url, {"status": "rejected", "reason": "Changed mind"}).status_code, 409)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_category_creation_and_cycle_rejection(self):
        self.client.force_login(self.catalog_user)
        root_response = self.post_json("/api/v1/operations/categories/", {"name": "کالای دیجیتال", "reason": "Launch taxonomy"})
        self.assertEqual(root_response.status_code, 201)
        root_id = root_response.json()["category"]["id"]
        child_response = self.post_json("/api/v1/operations/categories/", {"name": "موبایل", "parent_id": root_id, "reason": "Launch taxonomy"})
        self.assertEqual(child_response.status_code, 201)
        child_id = child_response.json()["category"]["id"]
        cycle_response = self.client.patch(
            f"/api/v1/operations/categories/{root_id}/",
            json.dumps({"parent_id": child_id, "reason": "Restructure taxonomy"}),
            content_type="application/json",
        )
        self.assertEqual(cycle_response.status_code, 400)
        self.assertIsNone(Category.objects.get(pk=root_id).parent_id)
        self.assertEqual(AuditEvent.objects.filter(action="category_created").count(), 2)
        self.assertEqual(AuditEvent.objects.filter(action="category_updated").count(), 0)

    def test_only_system_admin_changes_staff_roles(self):
        url = f"/api/v1/operations/staff/{self.buyer.pk}/roles/"
        payload = {"roles": ["finance_operator"], "reason": "Finance team onboarding"}
        self.client.force_login(self.manager)
        self.assertEqual(self.post_json(url, payload).status_code, 403)
        self.client.force_login(self.system_user)
        self.assertEqual(self.post_json(url, payload).status_code, 409)
        self.buyer.set_password("unique-staff-password")
        self.buyer.save(update_fields=["password"])
        self.assertEqual(self.post_json(url, payload).status_code, 200)
        self.buyer.refresh_from_db()
        self.assertTrue(self.buyer.is_staff)
        self.assertTrue(self.buyer.groups.filter(name="finance_operator").exists())
        self.assertEqual(AuditEvent.objects.get(action="staff_roles_changed").actor, self.system_user)
        self.assertEqual(self.post_json(f"/api/v1/operations/staff/{self.system_user.pk}/roles/", payload).status_code, 409)

    def test_audit_read_is_restricted(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get("/api/v1/operations/audit/").status_code, 403)
        self.client.force_login(self.system_user)
        self.assertEqual(self.client.get("/api/v1/operations/audit/").status_code, 200)

    def test_mutations_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        seller = Seller.objects.create(name="CSRF test")
        response = client.post(
            f"/api/v1/operations/sellers/{seller.pk}/decision/",
            json.dumps({"status": "approved", "reason": "Documents verified"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
