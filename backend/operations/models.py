from django.conf import settings
from uuid import uuid4
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="audit_events")
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=80)
    reason = models.CharField(max_length=500)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=["target_type", "target_id"])]

    def __str__(self):
        return f"{self.action} {self.target_type}:{self.target_id}"


class SupportTicket(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="support_tickets")
    order = models.ForeignKey("commerce.Order", null=True, blank=True, on_delete=models.PROTECT)
    subject = models.CharField(max_length=200)
    status = models.CharField(max_length=24, choices=(("open", "Open"), ("awaiting_customer", "Awaiting customer"), ("resolved", "Resolved"), ("closed", "Closed")), default="open")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_tickets")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    priority = models.CharField(max_length=10, choices=(("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")), default="normal")
    is_escalated = models.BooleanField(default=False)


class TicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.PROTECT, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    body = models.TextField()
    link = models.CharField(max_length=500, default="/account/")
    event_key = models.CharField(max_length=200, unique=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ContentPage(models.Model):
    slug = models.SlugField(max_length=200, unique=True, allow_unicode=True)
    title = models.CharField(max_length=200)
    body = models.TextField()
    kind = models.CharField(max_length=20, choices=(("guide", "Guide"), ("policy", "Policy"), ("campaign", "Campaign")), default="guide")
    is_published = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    publish_after = models.DateTimeField(null=True, blank=True)
    publish_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(version__gt=0), name="content_version_positive"), models.CheckConstraint(condition=models.Q(publish_after__isnull=True) | models.Q(publish_until__isnull=True) | models.Q(publish_until__gt=models.F("publish_after")), name="content_publication_window_order")]


class ContentRevision(models.Model):
    page = models.ForeignKey(ContentPage, on_delete=models.PROTECT, related_name="revisions")
    version = models.PositiveIntegerField()
    snapshot = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["page", "version"], name="unique_content_revision"), models.CheckConstraint(condition=models.Q(version__gt=0), name="content_revision_positive")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Content revisions are immutable")
        return super().save(*args, **kwargs)


class OutboxEvent(models.Model):
    event_key = models.CharField(max_length=200, unique=True)
    topic = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=12, choices=(("pending", "Pending"), ("done", "Done"), ("dead", "Dead")), default="pending")
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "available_at"])]


class OrderDispute(models.Model):
    delivery = models.OneToOneField("commerce.OrderDelivery", on_delete=models.PROTECT, related_name="dispute")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=2000)
    status = models.CharField(max_length=20, choices=(("open", "Open"), ("seller_responded", "Seller responded"), ("escalated", "Escalated"), ("resolved", "Resolved"), ("rejected", "Rejected")), default="open")
    seller_response = models.CharField(max_length=2000, blank=True)
    resolution = models.CharField(max_length=1000, blank=True)
    internal_note = models.CharField(max_length=1000, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="reviewed_disputes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preference")
    marketing_in_app = models.BooleanField(default=False)
    revision = models.UUIDField(default=uuid4)
    updated_at = models.DateTimeField(auto_now=True)


class MarketingCampaign(models.Model):
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=2000)
    link = models.CharField(max_length=500)
    recipient_limit = models.PositiveIntegerField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=(("draft", "Draft"), ("dispatching", "Dispatching"), ("queued", "Audience queued"), ("cancelled", "Cancelled")), default="draft")
    after_preference_id = models.PositiveBigIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="campaign_window_ordered"), models.CheckConstraint(condition=models.Q(recipient_limit__gte=1, recipient_limit__lte=10000), name="campaign_recipient_limit")]


class CampaignRecipient(models.Model):
    campaign = models.ForeignKey(MarketingCampaign, on_delete=models.PROTECT, related_name="recipients")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    preference_revision = models.UUIDField()
    status = models.CharField(max_length=12, choices=(("queued", "Queued"), ("delivered", "Delivered"), ("skipped", "Skipped")), default="queued")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["campaign", "user"], name="unique_campaign_recipient")]


class OrderRiskCase(models.Model):
    order = models.ForeignKey("commerce.Order", on_delete=models.PROTECT, related_name="risk_cases")
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_key = models.UUIDField()
    category = models.CharField(max_length=24, choices=(("payment_abuse", "Payment abuse"), ("account_takeover", "Account takeover"), ("delivery_abuse", "Delivery abuse"), ("other", "Other")))
    severity = models.CharField(max_length=10, choices=(("low", "Low"), ("medium", "Medium"), ("high", "High")))
    description = models.CharField(max_length=2000)
    hold_fulfillment = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=(("open", "Open"), ("escalated", "Escalated"), ("cleared", "Cleared")), default="open")
    outcome = models.CharField(max_length=12, blank=True, choices=(("dismissed", "Dismissed"), ("confirmed", "Confirmed")))
    resolution = models.CharField(max_length=1000, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="reviewed_risk_cases")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["opened_by", "request_key"], name="unique_risk_case_request")]


class SupportWriteReceipt(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_key = models.UUIDField()
    payload_digest = models.CharField(max_length=64)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.PROTECT)
    response_status = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["actor", "request_key"], name="unique_support_write_request")]
