from django.db import models


class PaymentAttempt(models.Model):
    class Provider(models.TextChoices):
        CARD = "card_gateway", "Card gateway"
        TARA = "tara", "Tara"
        SNAPP_PAY = "snapp_pay", "SnappPay"
        DIGIPAY = "digipay", "DigiPay"

    class Status(models.TextChoices):
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
    idempotency_key = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
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
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Ledger entries are immutable")
        if self.amount_toman == 0:
            raise ValueError("Ledger amount cannot be zero")
        return super().save(*args, **kwargs)
