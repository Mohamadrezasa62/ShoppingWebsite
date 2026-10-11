from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from .events import emit
from .models import MarketingCampaign, CampaignRecipient, NotificationPreference, Notification, AuditEvent


@transaction.atomic
def set_preference(user, enabled):
    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    if not user.is_active:
        raise ValueError("account_unavailable")
    preference, _ = NotificationPreference.objects.get_or_create(user=user, defaults={"revision": uuid4()})
    if preference.marketing_in_app != enabled:
        before = preference.marketing_in_app
        preference.marketing_in_app, preference.revision = enabled, uuid4()
        preference.save(update_fields=["marketing_in_app", "revision", "updated_at"])
        AuditEvent.objects.create(actor=user, action="notification_consent_changed", target_type="user", target_id=str(user.pk), reason="Customer changed in-app marketing consent", before={"marketing_in_app": before}, after={"marketing_in_app": enabled})
    return preference


@transaction.atomic
def campaign_action(campaign_id, action):
    row = MarketingCampaign.objects.select_for_update().get(pk=campaign_id)
    if action == "launch" and row.status == "draft" and row.ends_at > timezone.now():
        row.status = "dispatching"
        row.save(update_fields=["status"])
        event = emit(f"campaign:{row.pk}:scan:0", "campaign.scan", campaign_id=row.pk, after_id=0)
        event.available_at = max(timezone.now(), row.starts_at)
        event.save(update_fields=["available_at"])
    elif action == "cancel" and row.status in ("draft", "dispatching", "queued"):
        row.status = "cancelled"
        row.save(update_fields=["status"])
    elif not (action == "cancel" and row.status == "cancelled"):
        raise ValueError("invalid_campaign_transition")
    return row


def scan_campaign(campaign_id, after_id):
    # Invoked inside the outbox handler savepoint; all recipients/events commit together.
    row = MarketingCampaign.objects.select_for_update().get(pk=campaign_id)
    if row.status != "dispatching" or row.after_preference_id != after_id:
        return
    now = timezone.now()
    if now >= row.ends_at:
        row.status = "queued"
        row.save(update_fields=["status"])
        return
    if now < row.starts_at:
        raise ValueError("campaign_not_started")
    remaining = row.recipient_limit - row.recipients.count()
    size = min(100, remaining)
    preferences = list(NotificationPreference.objects.select_for_update(of=("self",)).filter(pk__gt=after_id, marketing_in_app=True, user__is_active=True).order_by("pk")[:size]) if size > 0 else []
    for preference in preferences:
        recipient, created = CampaignRecipient.objects.get_or_create(campaign=row, user_id=preference.user_id, defaults={"preference_revision": preference.revision})
        if created:
            emit(f"campaign-recipient:{recipient.pk}", "campaign.message", recipient_id=recipient.pk)
    if preferences:
        row.after_preference_id = preferences[-1].pk
    if not preferences or len(preferences) < size or row.recipients.count() >= row.recipient_limit:
        row.status = "queued"
    else:
        emit(f"campaign:{row.pk}:scan:{row.after_preference_id}", "campaign.scan", campaign_id=row.pk, after_id=row.after_preference_id)
    row.save(update_fields=["status", "after_preference_id"])


def deliver_recipient(recipient_id):
    reference = CampaignRecipient.objects.filter(pk=recipient_id).values("campaign_id", "user_id").first()
    if reference is None:
        return
    campaign = MarketingCampaign.objects.select_for_update().get(pk=reference["campaign_id"])
    user = get_user_model().objects.select_for_update().filter(pk=reference["user_id"]).first()
    if user is None:
        return
    preference = NotificationPreference.objects.select_for_update().filter(user=user).first()
    recipient = CampaignRecipient.objects.select_for_update().get(pk=recipient_id)
    if recipient.status != "queued":
        return
    now = timezone.now()
    consented = preference and preference.marketing_in_app and preference.revision == recipient.preference_revision
    if campaign.status == "cancelled" or not campaign.starts_at <= now < campaign.ends_at or not user.is_active or not consented:
        recipient.status = "skipped"
    else:
        Notification.objects.get_or_create(event_key=f"campaign-recipient:{recipient.pk}", defaults={"user": user, "title": campaign.title, "body": campaign.body, "link": campaign.link})
        recipient.status = "delivered"
    recipient.save(update_fields=["status"])
