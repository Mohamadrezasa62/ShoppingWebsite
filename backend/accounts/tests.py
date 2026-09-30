import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from sellers.models import Seller, SellerMembership


@override_settings(SMS_BACKEND="console")
class PhoneAuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("accounts.services.deliver_code")
    def test_code_creates_session_and_normalizes_phone(self, deliver_code):
        response = self.client.post(
            "/api/v1/auth/request-code/",
            data=json.dumps({"phone": "۰۹۱۲۳۴۵۶۷۸۹"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 202)
        phone, code = deliver_code.call_args.args
        self.assertEqual(phone, "+989123456789")

        response = self.client.post(
            "/api/v1/auth/verify-code/",
            data=json.dumps({"phone": "09123456789", "code": code.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get(phone=phone)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(self.client.get("/api/v1/auth/me/").json()["phone"], phone)

    @patch("accounts.services.deliver_code")
    def test_bad_code_is_limited(self, deliver_code):
        self.client.post(
            "/api/v1/auth/request-code/",
            data=json.dumps({"phone": "09123456789"}),
            content_type="application/json",
        )
        code = deliver_code.call_args.args[1]
        bad_code = "000000" if code != "000000" else "111111"
        for _ in range(5):
            response = self.client.post(
                "/api/v1/auth/verify-code/",
                data=json.dumps({"phone": "09123456789", "code": bad_code}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
        response = self.client.post(
            "/api/v1/auth/verify-code/",
            data=json.dumps({"phone": "09123456789", "code": code}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_code_request_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            "/api/v1/auth/request-code/",
            data=json.dumps({"phone": "09123456789"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    @patch("accounts.services.deliver_code")
    def test_staff_needs_password_as_second_factor(self, deliver_code):
        staff = get_user_model().objects.create_user("09123456784", "staff-password", is_staff=True)
        self.client.post(
            "/api/v1/auth/request-code/", json.dumps({"phone": staff.phone}), content_type="application/json"
        )
        code = deliver_code.call_args.args[1]
        path = "/api/v1/auth/verify-code/"
        without_password = self.client.post(path, json.dumps({"phone": staff.phone, "code": code}), content_type="application/json")
        self.assertEqual(without_password.status_code, 400)
        with_password = self.client.post(
            path, json.dumps({"phone": staff.phone, "code": code, "password": "staff-password"}), content_type="application/json"
        )
        self.assertEqual(with_password.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me/").json()["phone"], staff.phone)

    @override_settings(SMS_BACKEND="disabled")
    def test_no_sms_provider_does_not_issue_code(self):
        response = self.client.post(
            "/api/v1/auth/request-code/",
            data=json.dumps({"phone": "09123456789"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)


class PortalPermissionTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user("09123456789")
        self.staff = get_user_model().objects.create_user("09123456788", is_staff=True)
        self.seller_user = get_user_model().objects.create_user("09123456787")
        self.seller = Seller.objects.create(name="Test store", status=Seller.Status.APPROVED)
        SellerMembership.objects.create(seller=self.seller, user=self.seller_user, role=SellerMembership.Role.OWNER)

    def test_staff_finance_boundary(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get("/api/v1/admin/overview/").status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/api/v1/admin/overview/").status_code, 403)
        self.staff.groups.add(Group.objects.create(name="catalog_operator"))
        self.assertEqual(self.client.get("/api/v1/admin/overview/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/admin/finance/").status_code, 403)
        self.staff.groups.add(Group.objects.create(name="finance_operator"))
        self.assertEqual(self.client.get("/api/v1/admin/finance/").status_code, 200)

    def test_seller_store_status_visible_but_operations_require_approval(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get("/api/v1/seller/stores/").json()["stores"], [])
        self.client.force_login(self.seller_user)
        response = self.client.get("/api/v1/seller/stores/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stores"][0]["id"], self.seller.id)
        self.assertEqual(self.client.get(f"/api/v1/seller/stores/{self.seller.id}/offers/").status_code, 200)
        self.seller.status = Seller.Status.SUSPENDED
        self.seller.save()
        self.assertEqual(self.client.get("/api/v1/seller/stores/").json()["stores"][0]["status"], Seller.Status.SUSPENDED)
        self.assertEqual(self.client.get(f"/api/v1/seller/stores/{self.seller.id}/offers/").status_code, 403)

    def test_bootstrap_admin_can_open_user_creation(self):
        administrator = get_user_model().objects.create_superuser("09123456786", "long-development-password")
        self.client.force_login(administrator)
        self.assertEqual(self.client.get("/admin/accounts/user/add/").status_code, 200)
