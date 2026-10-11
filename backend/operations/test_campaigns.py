from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.utils import timezone
from .campaigns import campaign_action, set_preference
from .events import process_event
from .models import AuditEvent, CampaignRecipient, MarketingCampaign, Notification, NotificationPreference, OutboxEvent


class MarketingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("09123456501")
        self.other = get_user_model().objects.create_user("09123456502")
        self.admin = get_user_model().objects.create_user("09123456503", is_staff=True)
        self.admin.groups.add(Group.objects.create(name="marketplace_manager"))

    def campaign(self, limit=10, start=None):
        return MarketingCampaign.objects.create(title="Summer collection", body="Explore our summer products", link="/collections/summer/", recipient_limit=limit, starts_at=start or timezone.now()-timedelta(days=1), ends_at=timezone.now()+timedelta(days=1), created_by=self.admin)

    def queue(self, campaign):
        campaign_action(campaign.pk, "launch")
        scan = OutboxEvent.objects.get(event_key=f"campaign:{campaign.pk}:scan:0")
        self.assertTrue(process_event(scan.pk))
        return OutboxEvent.objects.filter(topic="campaign.message").order_by("pk").last()

    def test_preferences_require_explicit_consent_and_are_private(self):
        path = "/api/v1/operations/notification-preferences/"
        self.assertEqual(self.client.get(path).status_code, 401)
        self.client.force_login(self.user)
        self.assertFalse(self.client.get(path).json()["marketing_in_app"])
        bad = self.client.patch(path, json.dumps({"marketing_in_app": True, "user_id": self.other.pk}), content_type="application/json")
        self.assertEqual(bad.status_code, 400)
        first = set_preference(self.user, True)
        self.assertEqual(set_preference(self.user, True).revision, first.revision)
        self.assertEqual(AuditEvent.objects.filter(action="notification_consent_changed").count(), 1)
        set_preference(self.user, False)
        self.assertNotEqual(set_preference(self.user, True).revision, first.revision)
        self.client.force_login(self.other)
        self.assertFalse(self.client.get(path).json()["marketing_in_app"])
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.patch(path, "{}", content_type="application/json").status_code, 403)

    def test_only_active_opted_in_users_receive_one_notification(self):
        set_preference(self.user, True)
        set_preference(self.other, False)
        campaign = self.campaign()
        event = self.queue(campaign)
        self.assertEqual(CampaignRecipient.objects.count(), 1)
        self.assertTrue(process_event(event.pk))
        self.assertFalse(process_event(event.pk))
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Notification.objects.get().user_id, self.user.pk)
        self.assertEqual(CampaignRecipient.objects.get().status, "delivered")

    def test_withdrawn_consent_and_new_revision_suppress_old_queued_message(self):
        set_preference(self.user, True)
        event = self.queue(self.campaign())
        set_preference(self.user, False)
        set_preference(self.user, True)
        self.assertTrue(process_event(event.pk))
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(CampaignRecipient.objects.get().status, "skipped")

    def test_cancelled_expired_and_inactive_recipients_are_skipped(self):
        for outcome in ("cancel", "expired", "inactive"):
            self.user.is_active = True
            self.user.save(update_fields=["is_active"])
            set_preference(self.user, True)
            campaign = self.campaign()
            event = self.queue(campaign)
            if outcome == "cancel":
                campaign_action(campaign.pk, "cancel")
            elif outcome == "expired":
                MarketingCampaign.objects.filter(pk=campaign.pk).update(ends_at=timezone.now()-timedelta(seconds=1))
            else:
                self.user.is_active = False
                self.user.save(update_fields=["is_active"])
            self.assertTrue(process_event(event.pk))
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(CampaignRecipient.objects.filter(status="skipped").count(), 3)

    def test_future_campaign_is_scheduled_in_outbox(self):
        set_preference(self.user, True)
        campaign = self.campaign(start=timezone.now()+timedelta(hours=1))
        campaign_action(campaign.pk, "launch")
        event = OutboxEvent.objects.get(topic="campaign.scan")
        self.assertFalse(process_event(event.pk))
        self.assertFalse(CampaignRecipient.objects.exists())
        event.refresh_from_db()
        self.assertEqual(event.attempts, 0)

    def test_batch_cursor_and_recipient_limit_prevent_duplicates(self):
        users = [get_user_model().objects.create_user(f"0912345{n:04d}") for n in range(103)]
        NotificationPreference.objects.bulk_create([NotificationPreference(user=user, marketing_in_app=True) for user in users])
        campaign = self.campaign(limit=101)
        self.queue(campaign)
        self.assertEqual(CampaignRecipient.objects.count(), 100)
        pending = OutboxEvent.objects.get(topic="campaign.scan", status="pending")
        self.assertTrue(process_event(pending.pk))
        self.assertEqual(CampaignRecipient.objects.count(), 101)
        for pk in list(OutboxEvent.objects.filter(topic="campaign.message").values_list("pk", flat=True)):
            self.assertTrue(process_event(pk))
        self.assertEqual(Notification.objects.count(), 101)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, "queued")

    def test_handler_failure_rolls_back_message_and_retry_does_not_duplicate(self):
        set_preference(self.user, True)
        event = self.queue(self.campaign())
        original = Notification.objects.get_or_create
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("Transport failure")
        with patch.object(Notification.objects, "get_or_create", side_effect=fail):
            self.assertFalse(process_event(event.pk))
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(CampaignRecipient.objects.get().status, "queued")
        OutboxEvent.objects.filter(pk=event.pk).update(available_at=timezone.now())
        self.assertTrue(process_event(event.pk))
        self.assertEqual(Notification.objects.count(), 1)

    def test_campaign_api_rejects_external_links_and_unauthorized_actions(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/api/v1/operations/campaigns/").status_code, 403)
        self.client.force_login(self.admin)
        payload = {"title": "Campaign", "body": "Campaign body", "link": "https://example.com/", "recipient_limit": 1, "starts_at": timezone.now().isoformat(), "ends_at": (timezone.now()+timedelta(days=1)).isoformat(), "reason": "Approved campaign"}
        result = self.client.post("/api/v1/operations/campaigns/", json.dumps(payload), content_type="application/json")
        self.assertEqual(result.status_code, 400)
        payload["link"] = "/collections/summer/"
        result = self.client.post("/api/v1/operations/campaigns/", json.dumps(payload), content_type="application/json")
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()["campaign"]["status"], "draft")
        self.assertFalse(OutboxEvent.objects.exists())
