from dataclasses import dataclass
from django.db import transaction
from django.utils import timezone

from catalog.models import Offer
from commerce.models import Order, OrderLine

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
                if offer.reserved_quantity < line.quantity or offer.available_quantity < line.quantity:
                    payable = False
                    break
            if payable:
                for line in lines:
                    offer = offers[line.offer_id]
                    offer.reserved_quantity -= line.quantity
                    offer.available_quantity -= line.quantity
                    offer.save(update_fields=["reserved_quantity", "available_quantity"])
                order.status = Order.Status.PAID
                order.save(update_fields=["status"])
        attempt.status = PaymentAttempt.Status.CAPTURED if payable else PaymentAttempt.Status.REVIEW_REQUIRED
        attempt.save(update_fields=["provider_reference", "status", "updated_at"])
        return payable
