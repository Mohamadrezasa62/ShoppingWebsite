import json
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from catalog.models import Offer
from sellers.models import Seller


class FoundationTests(TestCase):
    def test_revoke_all_sessions_invalidates_other_devices(self):
        user = get_user_model().objects.create_user("09123456780")
        other_device = Client()
        self.client.force_login(user)
        other_device.force_login(user)
        self.assertEqual(self.client.post("/api/v1/auth/revoke-sessions/").status_code, 200)
        self.assertEqual(other_device.get("/api/v1/auth/me/").status_code, 401)
        other_device.force_login(get_user_model().objects.get(pk=user.pk))
        self.assertEqual(other_device.get("/api/v1/auth/me/").status_code, 200)

    def test_profile_rejects_privilege_and_phone_changes(self):
        user = get_user_model().objects.create_user("09123456780")
        self.client.force_login(user)
        for data in ({"is_staff": True}, {"phone": "09123456781"}, {"first_name": 123}):
            self.assertEqual(self.client.patch("/api/v1/auth/me/", json.dumps(data), content_type="application/json").status_code, 400)
        result = self.client.patch("/api/v1/auth/me/", json.dumps({"first_name": "  علی  "}), content_type="application/json")
        self.assertEqual(result.json()["first_name"], "علی")
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        self.assertEqual(client.patch("/api/v1/auth/me/", "{}", content_type="application/json").status_code, 403)

    def test_request_ids_are_bounded_and_private_responses_not_cached(self):
        response = self.client.get("/api/v1/auth/me/", HTTP_X_REQUEST_ID="safe-id")
        self.assertEqual(response["X-Request-ID"], "safe-id")
        self.assertEqual(response["Cache-Control"], "no-store")
        response = self.client.get("/api/v1/auth/me/", HTTP_X_REQUEST_ID="x" * 1000)
        self.assertEqual(len(response["X-Request-ID"]), 32)

    @override_settings(DEBUG=True)
    def test_demo_seed_is_repeatable(self):
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Seller.objects.count(), 2)
        self.assertEqual(Offer.objects.count(), 2)
        self.assertFalse(get_user_model().objects.filter(is_staff=True).exists())

    @override_settings(DEBUG=False)
    def test_demo_seed_disabled_in_production(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo")


class ExportPrivacyTests(TestCase):
    def test_export_includes_only_owner_records_and_excludes_internal_notes(self):
        import json
        from django.contrib.auth import get_user_model
        from operations.models import SupportTicket, TicketMessage
        user = get_user_model().objects.create_user("09123456981")
        other = get_user_model().objects.create_user("09123456982")
        ticket = SupportTicket.objects.create(user=user, subject="My ticket")
        TicketMessage.objects.create(ticket=ticket, author=user, body="Visible message")
        TicketMessage.objects.create(ticket=ticket, author=other, body="Private staff note", is_internal=True)
        SupportTicket.objects.create(user=other, subject="Other user secret")
        self.assertEqual(self.client.get("/api/v1/auth/export/").status_code, 401)
        self.client.force_login(user)
        response = self.client.get("/api/v1/auth/export/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("Visible message", body)
        self.assertNotIn("Private staff note", body)
        self.assertNotIn("Other user secret", body)
        self.assertNotIn("password", response.json()["profile"])
        self.assertEqual(response["Cache-Control"], "no-store")


class OtpConsumptionTests(TestCase):
    def test_atomic_consumption_marker_rejects_duplicate_stale_reads(self):
        from django.core.cache import cache
        from unittest.mock import patch
        from accounts.services import _code_digest, consume_code
        cache.clear()
        phone, code = "+989123456985", "123456"
        record = {"digest": _code_digest(phone, code), "nonce": "unique-nonce"}
        cache.set(f"otp:code:{phone}", record, 300)
        # Keep the record visible as if the second worker read it before deletion.
        with patch.object(cache, "delete"):
            self.assertTrue(consume_code(phone, code=code))
            self.assertFalse(consume_code(phone, code=code))
        cache.clear()

    def test_changed_code_cannot_be_consumed_after_initial_validation(self):
        from django.core.cache import cache
        from accounts.services import _code_digest, consume_code
        cache.clear()
        phone = "+989123456985"
        cache.set(f"otp:code:{phone}", {"digest": _code_digest(phone, "654321"), "nonce": "replacement"}, 300)
        self.assertFalse(consume_code(phone, code="123456"))
        self.assertTrue(consume_code(phone, code="654321"))
        cache.clear()


class BrowserFixtureGuardTests(TestCase):
    @override_settings(DEBUG=False)
    def test_fixture_command_cannot_create_sessions_in_production(self):
        with self.assertRaises(CommandError):
            call_command("seed_e2e", output="unused-e2e-file.json")
