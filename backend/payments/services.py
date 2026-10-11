from dataclasses import dataclass
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from catalog.models import Offer
from catalog.inventory import can_consume, finish_line
from commerce.models import Order, OrderLine

from operations.events import emit
from .models import LedgerEntry, PaymentAttempt


@dataclass(frozen=True)
class VerifiedCapture:
    """A result obtained by a trusted server-to-server provider verification."""

    provider_reference: str
    amount_toman: int
    currency: str


def record_verified_capture(attempt_id: int, capture: VerifiedCapture) -> bool:
    """Record money received, then fulfill the order only when it is still payable.

    Never call this with browser callback parameters. An authenticated provider
    adapter must first verify the transaction directly with the provider.
    """
    if not capture.provider_reference or capture.amount_toman <= 0 or capture.currency != "TOMAN":
        raise ValueError("Invalid verified capture")
    with transaction.atomic():
        # Lock order before attempt, matching order expiry's lock order.
        order_id = PaymentAttempt.objects.values_list("order_id", flat=True).get(pk=attempt_id)
        order = Order.objects.select_for_update().get(pk=order_id)
        attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
        if attempt.status in (PaymentAttempt.Status.CAPTURED, PaymentAttempt.Status.REVIEW_REQUIRED):
            if attempt.provider_reference != capture.provider_reference:
                raise ValueError("Conflicting payment reference")
            recorded = LedgerEntry.objects.get(attempt=attempt, kind=LedgerEntry.Kind.PAYMENT_CAPTURE)
            if recorded.amount_toman != capture.amount_toman:
                raise ValueError("Conflicting captured amount")
            return attempt.status == PaymentAttempt.Status.CAPTURED
        if attempt.provider_reference and attempt.provider_reference != capture.provider_reference:
            raise ValueError("Conflicting payment reference")
        attempt.provider_reference = capture.provider_reference
        LedgerEntry.objects.create(
            order=order, attempt=attempt, kind=LedgerEntry.Kind.PAYMENT_CAPTURE,
            amount_toman=capture.amount_toman,
            event_key=f"capture:{attempt.provider}:{capture.provider_reference}",
        )
        payable = (
            order.status == Order.Status.PENDING_PAYMENT
            and order.expires_at > timezone.now()
            and attempt.amount_toman == order.grand_total_toman == capture.amount_toman
        )
        if payable:
            lines = list(OrderLine.objects.filter(delivery__order=order))
            offers = {offer.pk: offer for offer in Offer.objects.select_for_update().filter(
                pk__in=[line.offer_id for line in lines]
            ).order_by("pk")}
            for line in lines:
                offer = offers[line.offer_id]
                if not can_consume(offer, line):
                    payable = False
                    break
            if payable:
                for line in lines:
                    offer = offers[line.offer_id]
                    finish_line(offer, line, consume=True)
                order.status = Order.Status.PAID
                order.save(update_fields=["status"])
                emit(f"order:{order.pk}:paid", "order.paid", order_id=order.pk)
        attempt.status = PaymentAttempt.Status.CAPTURED if payable else PaymentAttempt.Status.REVIEW_REQUIRED
        attempt.save(update_fields=["provider_reference", "status", "updated_at"])
        return payable


def record_verified_refund(attempt_id: int, provider_refund_reference: str, amount_toman: int) -> LedgerEntry:
    """Record a provider-confirmed refund without allowing more than captured."""
    if not provider_refund_reference or amount_toman <= 0:
        raise ValueError("Invalid verified refund")
    with transaction.atomic():
        order_id = PaymentAttempt.objects.values_list("order_id", flat=True).get(pk=attempt_id)
        order = Order.objects.select_for_update().get(pk=order_id)
        attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
        event_key = f"refund:{attempt.provider}:{provider_refund_reference}"
        existing = LedgerEntry.objects.filter(event_key=event_key).first()
        if existing:
            if existing.attempt_id != attempt_id or existing.amount_toman != -amount_toman:
                raise ValueError("Conflicting refund reference")
            return existing
        captured = LedgerEntry.objects.filter(
            attempt=attempt, kind=LedgerEntry.Kind.PAYMENT_CAPTURE,
        ).aggregate(total=Sum("amount_toman"))["total"] or 0
        refunded = -(LedgerEntry.objects.filter(
            attempt=attempt, kind=LedgerEntry.Kind.PAYMENT_REFUND,
        ).aggregate(total=Sum("amount_toman"))["total"] or 0)
        if captured == 0 or refunded + amount_toman > captured:
            raise ValueError("Refund exceeds captured payment")
        return LedgerEntry.objects.create(
            order=order, attempt=attempt, kind=LedgerEntry.Kind.PAYMENT_REFUND,
            amount_toman=-amount_toman, event_key=event_key,
        )
