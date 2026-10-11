from uuid import UUID
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from commerce.models import Order
from .models import PaymentAttempt
from .services import VerifiedCapture, record_verified_capture


class PaymentError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status


def sandbox_enabled():
    return settings.DEBUG and settings.ENABLE_SANDBOX_PAYMENTS


def initiate_sandbox(user, order_id, request_key):
    if not sandbox_enabled():
        raise PaymentError("provider_unavailable", 503)
    try:
        key = UUID(str(request_key))
    except (ValueError, TypeError, AttributeError):
        raise PaymentError("invalid_idempotency_key", 400)
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
        if order is None:
            raise PaymentError("order_not_found", 404)
        existing = PaymentAttempt.objects.filter(order=order, idempotency_key=key).first()
        if existing:
            if existing.provider != "sandbox":
                raise PaymentError("idempotency_conflict")
            return existing
        if order.status != Order.Status.PENDING_PAYMENT or order.expires_at <= timezone.now():
            raise PaymentError("order_not_payable")
        attempt = PaymentAttempt.objects.create(order=order, provider="sandbox", amount_toman=order.grand_total_toman, idempotency_key=key)
        attempt.provider_reference = f"sandbox-{attempt.pk}-{key}"
        attempt.checkout_url = f"/sandbox-payment/?attempt={attempt.pk}"
        attempt.status = PaymentAttempt.Status.REDIRECTED
        attempt.save(update_fields=["provider_reference", "checkout_url", "status", "updated_at"])
        return attempt


def simulate_result(user, attempt_id, outcome):
    if not sandbox_enabled():
        raise PaymentError("provider_unavailable", 503)
    attempt = PaymentAttempt.objects.filter(pk=attempt_id, order__user=user, provider="sandbox").first()
    if attempt is None:
        raise PaymentError("payment_not_found", 404)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=attempt.order_id)
        current = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
        if outcome == "success":
            if current.status == PaymentAttempt.Status.REJECTED:
                raise PaymentError("payment_rejected")
            record_verified_capture(current.pk, VerifiedCapture(current.provider_reference, current.amount_toman, "TOMAN"))
        elif outcome == "rejected":
            if current.status in (PaymentAttempt.Status.CAPTURED, PaymentAttempt.Status.REVIEW_REQUIRED):
                raise PaymentError("payment_already_verified")
            current.status = PaymentAttempt.Status.REJECTED
            current.save(update_fields=["status", "updated_at"])
        else:
            raise PaymentError("invalid_outcome", 400)
    attempt.refresh_from_db()
    return attempt
