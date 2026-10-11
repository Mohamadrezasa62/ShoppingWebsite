import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from operations.models import AuditEvent
from .services import _code_digest, consume_code, verified_challenge, verify_code, request_code, SmsUnavailable


@override_settings(DEBUG=True, SMS_BACKEND="console")
class AuthenticationSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = get_user_model().objects.create_user("09123456196", "Original-Staff-Password!84", is_staff=True)
        self.buyer = get_user_model().objects.create_user("09123456197")
        self.client.force_login(self.staff)
        self.new = "Different-Staff-Secret!97"
        self.path = "/api/v1/auth/staff-password/"

    def post(self, path, data=None, **extra):
        return self.client.post(path, json.dumps(data or {}), content_type="application/json", **extra)

    def code(self):
        with patch("accounts.services.deliver_code") as deliver:
            self.assertEqual(self.post(self.path+"request-code/").status_code, 202)
            return deliver.call_args.args[1]

    def change(self, code, **extra):
        return self.post(self.path+"change/", {"current_password": "Original-Staff-Password!84", "new_password": self.new, "code": code, **extra})

    def record(self, purpose="login", nonce="challenge", code="123456"):
        scope = self.staff.phone if purpose == "login" else f"{purpose}:{self.staff.phone}"
        cache.set(f"otp:code:{scope}", {"digest": _code_digest(self.staff.phone, code, purpose), "nonce": nonce}, 300)
        return code

    def test_password_rotation_revokes_all_sessions_without_auditing_secrets(self):
        other = Client()
        other.force_login(self.staff)
        code = self.code()
        self.assertEqual(self.change(code).status_code, 200)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password(self.new))
        self.assertEqual(self.staff.session_version, 1)
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)
        self.assertEqual(other.get("/api/v1/auth/me/").status_code, 401)
        audit = AuditEvent.objects.get(action="staff_password_changed")
        serialized = json.dumps({"reason": audit.reason, "before": audit.before, "after": audit.after})
        self.assertNotIn(self.new, serialized)
        self.assertNotIn(code, serialized)
        self.assertNotIn(self.staff.password, serialized)

    def test_purpose_isolation_prevents_login_and_rotation_code_reuse(self):
        code = self.record("staff_password")
        self.assertFalse(verify_code(self.staff.phone, code))
        cache.delete(f"otp:code:staff_password:{self.staff.phone}")
        self.record("login")
        self.assertEqual(self.change(code).status_code, 400)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password("Original-Staff-Password!84"))
        self.assertFalse(AuditEvent.objects.exists())

    def test_wrong_old_password_and_weak_new_password_never_mutate_account(self):
        code = self.code()
        self.assertEqual(self.change(code, current_password="Wrong-password").json()["error"], "invalid_credentials")
        self.assertEqual(self.change(code, new_password="123").json()["error"], "weak_password")
        self.assertEqual(self.change(code, new_password="Original-Staff-Password!84").json()["error"], "password_unchanged")
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.session_version, 0)
        self.assertFalse(AuditEvent.objects.exists())
        self.assertEqual(self.change(code).status_code, 200)

    def test_buyers_anonymous_users_and_csrf_failures_cannot_rotate_staff_password(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.post(self.path+"request-code/").status_code, 403)
        self.assertEqual(self.change("123456").status_code, 403)
        self.client.logout()
        self.assertEqual(self.post(self.path+"request-code/").status_code, 401)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.staff)
        self.assertEqual(csrf.post(self.path+"request-code/", "{}", content_type="application/json").status_code, 403)
        self.assertEqual(csrf.post(self.path+"change/", "{}", content_type="application/json").status_code, 403)

    def test_audit_failure_rolls_back_password_but_consumed_code_requires_new_challenge(self):
        code = self.code()
        with patch("accounts.password_views.AuditEvent.objects.create", side_effect=RuntimeError("Audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.change(code)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password("Original-Staff-Password!84"))
        self.assertEqual(self.staff.session_version, 0)
        self.assertEqual(self.change(code).status_code, 400)
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)

    def test_invalid_payload_and_disabled_sms(self):
        for payload in [{}, {"current_password": None, "new_password": self.new, "code": "123456"}, {"current_password": "x", "new_password": self.new, "code": "bad"}, {"current_password": "x", "new_password": self.new, "code": "123456", "user_id": self.buyer.pk}]:
            self.assertEqual(self.post(self.path+"change/", payload).status_code, 400)
        with override_settings(SMS_BACKEND="disabled"):
            self.assertEqual(self.post(self.path+"request-code/").status_code, 503)

    def test_ip_limits_cannot_be_bypassed_with_forwarded_header(self):
        self.client.logout()
        with patch("accounts.services.deliver_code"):
            for index in range(20):
                response = self.post("/api/v1/auth/request-code/", {"phone": f"0912000{index:04d}"}, HTTP_X_FORWARDED_FOR=f"192.0.2.{index}")
                self.assertEqual(response.status_code, 202)
            rejected = self.post("/api/v1/auth/request-code/", {"phone": "09120009999"}, HTTP_X_FORWARDED_FOR="203.0.113.5")
            self.assertEqual(rejected.status_code, 429)
            self.assertTrue(1 <= int(rejected["Retry-After"]) <= 600)
            self.assertEqual(self.post("/api/v1/auth/request-code/", {"phone": "09120009998"}, REMOTE_ADDR="192.0.2.200").status_code, 202)

    def test_verification_ip_limit_applies_even_when_no_code_exists(self):
        self.client.logout()
        for _ in range(100):
            self.assertEqual(self.post("/api/v1/auth/verify-code/", {"phone": self.staff.phone, "code": "123456"}).status_code, 400)
        self.assertEqual(self.post("/api/v1/auth/verify-code/", {"phone": self.staff.phone, "code": "123456"}).status_code, 429)

    def test_cache_outage_fails_closed_without_creating_account(self):
        self.client.logout()
        with patch("accounts.throttling.cache.add", side_effect=ConnectionError("Cache offline")):
            self.assertEqual(self.post("/api/v1/auth/request-code/", {"phone": "09120009999"}).status_code, 503)
            self.assertEqual(self.post("/api/v1/auth/verify-code/", {"phone": "09120009999", "code": "123456"}).status_code, 503)
        self.assertFalse(get_user_model().objects.filter(phone="+989120009999").exists())
        self.record()
        with patch("accounts.services.cache.get", side_effect=ConnectionError("Cache read offline")):
            self.assertEqual(self.post("/api/v1/auth/verify-code/", {"phone": self.staff.phone, "code": "123456"}).status_code, 503)

    def test_replaced_identical_code_cannot_consume_new_nonce(self):
        code = self.record(nonce="old")
        nonce = verified_challenge(self.staff.phone, code)
        self.record(nonce="new", code=code)
        self.assertFalse(consume_code(self.staff.phone, expected_nonce=nonce, code=code))
        self.assertTrue(verify_code(self.staff.phone, code))
        self.assertFalse(verify_code(self.staff.phone, code))

    def test_delayed_consumer_does_not_delete_replacement_code(self):
        code = self.record(nonce="old")
        original_add = cache.add
        def replace_then_consume(key, value, timeout):
            if key.endswith(":old") and key.startswith("otp:consumed:"):
                self.record(nonce="new", code="654321")
            return original_add(key, value, timeout)
        with patch("accounts.services.cache.add", side_effect=replace_then_consume):
            self.assertTrue(consume_code(self.staff.phone, expected_nonce="old", code=code))
        self.assertTrue(verify_code(self.staff.phone, "654321"))

    def test_failed_delivery_does_not_delete_newer_challenge(self):
        def failed_delivery(phone, code, *, purpose):
            self.record(nonce="replacement", code="654321")
            raise SmsUnavailable()
        with patch("accounts.services.deliver_code", side_effect=failed_delivery):
            with self.assertRaises(SmsUnavailable):
                request_code(self.staff.phone)
        self.assertTrue(verify_code(self.staff.phone, "654321"))

    def test_failed_consumption_rolls_back_new_account_creation(self):
        self.client.logout()
        phone = "+989120009999"
        cache.set(f"otp:code:{phone}", {"digest": _code_digest(phone, "123456"), "nonce": "new-user"}, 300)
        with patch("accounts.views.consume_code", return_value=False):
            self.assertEqual(self.post("/api/v1/auth/verify-code/", {"phone": phone, "code": "123456"}).status_code, 400)
        self.assertFalse(get_user_model().objects.filter(phone=phone).exists())
