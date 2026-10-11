from django.db import models


class PaymentAttempt(models.Model):
    class Provider(models.TextChoices):
        SANDBOX = "sandbox", "Development simulation"
        ZARINPAL = "zarinpal", "Zarinpal"
        CARD = "card_gateway", "Card gateway"
        TARA = "tara", "Tara"
        SNAPP_PAY = "snapp_pay", "SnappPay"
        DIGIPAY = "digipay", "DigiPay"

    class Status(models.TextChoices):
        INITIATION_UNKNOWN = "initiation_unknown", "Initiation requires reconciliation"
        CREATED = "created", "Created"
        REDIRECTED = "redirected", "Redirected"
        VERIFYING = "verifying", "Verifying"
        CAPTURED = "captured", "Captured"
        REJECTED = "rejected", "Rejected"
        REVIEW_REQUIRED = "review_required", "Review required"

    order = models.ForeignKey("commerce.Order", on_delete=models.PROTECT, related_name="payment_attempts")
    provider = models.CharField(max_length=20, choices=Provider.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    amount_toman = models.PositiveBigIntegerField()
    provider_reference = models.CharField(max_length=160, blank=True)
    gateway_authority = models.CharField(max_length=160, blank=True)
    gateway_merchant = models.CharField(max_length=64, blank=True)
    callback_token = models.CharField(max_length=64, blank=True)
    checkout_url = models.CharField(max_length=1000, blank=True)
    idempotency_key = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["callback_token"], condition=~models.Q(callback_token=""), name="unique_payment_callback_token"),
            models.UniqueConstraint(fields=["provider", "gateway_authority"], condition=~models.Q(gateway_authority=""), name="unique_gateway_authority"),
            models.UniqueConstraint(fields=["order", "idempotency_key"], name="unique_payment_attempt_request"),
            models.UniqueConstraint(
                fields=["provider", "provider_reference"], condition=~models.Q(provider_reference=""),
                name="unique_provider_payment_reference",
            ),
        ]


class LedgerEntry(models.Model):
    class Kind(models.TextChoices):
        PAYMENT_CAPTURE = "payment_capture", "Payment capture"
        PAYMENT_REFUND = "payment_refund", "Payment refund"
        SELLER_PAYABLE = "seller_payable", "Seller payable"
        COMMISSION = "commission", "Commission"

    order = models.ForeignKey("commerce.Order", on_delete=models.PROTECT, related_name="ledger_entries")
    attempt = models.ForeignKey(PaymentAttempt, null=True, blank=True, on_delete=models.PROTECT, related_name="ledger_entries")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    amount_toman = models.BigIntegerField()
    event_key = models.CharField(max_length=160, unique=True)
    seller = models.ForeignKey("sellers.Seller", null=True, blank=True, on_delete=models.PROTECT, related_name="ledger_entries")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Ledger entries are immutable")
        if self.amount_toman == 0:
            raise ValueError("Ledger amount cannot be zero")
        return super().save(*args, **kwargs)


class Settlement(models.Model):
    seller = models.ForeignKey("sellers.Seller", on_delete=models.PROTECT, related_name="settlements")
    amount_toman = models.PositiveBigIntegerField()
    status = models.CharField(max_length=20, choices=(("draft", "Draft"), ("approved", "Approved"), ("cancelled", "Cancelled"), ("simulated_paid", "Simulated paid")), default="draft")
    idempotency_key = models.UUIDField()
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="created_settlements")
    entry_snapshot = models.JSONField(default=list)
    approved_by = models.ForeignKey("accounts.User", null=True, on_delete=models.PROTECT, related_name="approved_settlements")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["seller", "idempotency_key"], name="unique_seller_settlement_request")]


class SettlementLine(models.Model):
    settlement = models.ForeignKey(Settlement, on_delete=models.PROTECT, related_name="lines")
    ledger_entry = models.OneToOneField(LedgerEntry, on_delete=models.PROTECT, related_name="settlement_line")


class PaymentInvestigationNote(models.Model):
    attempt = models.ForeignKey(PaymentAttempt, on_delete=models.PROTECT, related_name='investigation_notes')
    actor = models.ForeignKey('accounts.User', on_delete=models.PROTECT)
    request_key = models.UUIDField()
    body = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['actor', 'request_key'], name='unique_payment_note_request')]
        indexes = [models.Index(fields=['attempt', '-id'], name='payment_note_page')]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('Payment investigation notes are append-only')
        return super().save(*args, **kwargs)
