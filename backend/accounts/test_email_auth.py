from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import Client, TestCase


class EmailAuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.password = "Astral!Pine_9382"

    def register(self, email="buyer@example.com", **overrides):
        return self.client.post("/api/v1/auth/email/register/", {"email": email, "password": self.password, "name": "Buyer", **overrides}, content_type="application/json")

    def test_email_only_registration_creates_hashed_password_and_session(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(email="buyer@example.com")
        self.assertIsNone(user.phone)
        self.assertTrue(user.check_password(self.password))
        self.assertNotEqual(user.password, self.password)
        self.assertEqual(self.client.get("/api/v1/auth/me/").json()["email"], user.email)

    def test_email_is_case_insensitive_and_duplicates_do_not_merge_accounts(self):
        self.assertEqual(self.register("Buyer@Example.com").status_code, 201)
        self.client.logout()
        self.assertEqual(self.register("BUYER@example.com").status_code, 409)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_database_enforces_case_insensitive_email_uniqueness(self):
        self.register()
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user(email="BUYER@example.com", password=self.password)

    def test_multiple_phone_accounts_without_email_remain_supported(self):
        for phone in ["+989123456781", "+989123456782"]:
            get_user_model().objects.create_user(phone=phone)
        self.assertEqual(get_user_model().objects.count(), 2)

    def test_login_with_email_without_sms(self):
        self.register()
        self.client.logout()
        response = self.client.post("/api/v1/auth/email/login/", {"email": "BUYER@example.com", "password": self.password}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)

    def test_invalid_and_inactive_credentials_are_rejected(self):
        self.register()
        self.client.logout()
        for email in ["buyer@example.com", "missing@example.com"]:
            response = self.client.post("/api/v1/auth/email/login/", {"email": email, "password": "incorrect"}, content_type="application/json")
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["error"], "invalid_credentials")
        get_user_model().objects.filter(email="buyer@example.com").update(is_active=False)
        self.assertEqual(self.client.post("/api/v1/auth/email/login/", {"email": "buyer@example.com", "password": self.password}, content_type="application/json").status_code, 401)

    def test_staff_cannot_skip_phone_verification_via_email(self):
        get_user_model().objects.create_user(phone="+989123456783", email="staff@example.com", password=self.password, is_staff=True)
        response = self.client.post("/api/v1/auth/email/login/", {"email": "staff@example.com", "password": self.password}, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "staff_phone_verification_required")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)

    def test_weak_password_and_invalid_email_are_rejected(self):
        self.assertEqual(self.register(password="12345678").status_code, 400)
        self.assertEqual(self.register(email="not-an-email").status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_csrf_is_required_for_both_email_endpoints(self):
        client = Client(enforce_csrf_checks=True)
        for action in ["login", "register"]:
            self.assertEqual(client.post(f"/api/v1/auth/email/{action}/", {}, content_type="application/json").status_code, 403)

    def test_email_login_records_current_session_revocation_version(self):
        user = get_user_model().objects.create_user(email="buyer@example.com", password=self.password, session_version=5)
        self.client.post("/api/v1/auth/email/login/", {"email": user.email, "password": self.password}, content_type="application/json")
        self.assertEqual(self.client.session["account_session_version"], 5)
