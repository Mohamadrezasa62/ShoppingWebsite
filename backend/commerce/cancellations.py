from django.db import transaction
from catalog.models import Offer
from catalog.inventory import InventoryError, restock_line
from operations.events import emit
from payments.models import PaymentAttempt
from payments.orchestration import sandbox_enabled
from payments.services import record_verified_refund
from .models import DeliveryCancellation, Order, OrderDelivery
from .services import CheckoutError

BEFORE_SHIPPING = ("awaiting_fulfillment", "packing")


def request_cancellation(user, delivery_id, reason):
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 2000:
        raise CheckoutError("invalid_cancellation", 400)
    reason = reason.strip()
    with transaction.atomic():
        reference = OrderDelivery.objects.filter(pk=delivery_id, order__user=user).values_list("order_id", flat=True).first()
        if reference is None:
            raise CheckoutError("delivery_not_found", 404)
        order = Order.objects.select_for_update().get(pk=reference)
        delivery = OrderDelivery.objects.select_for_update().get(pk=delivery_id)
        existing = DeliveryCancellation.objects.filter(delivery=delivery).first()
        if existing:
            if existing.reason != reason:
                raise CheckoutError("cancellation_conflict")
            return existing
        if order.status != "paid" or delivery.status not in BEFORE_SHIPPING:
            raise CheckoutError("delivery_not_cancellable")
        amount = sum(line.line_total_toman - line.discount_toman + line.tax_toman for line in delivery.lines.all()) + delivery.shipping_fee_toman
        case = DeliveryCancellation.objects.create(delivery=delivery, requested_by=user, reason=reason, amount_toman=amount)
        emit(f"cancellation:{case.pk}:requested", "cancellation.requested", order_id=order.pk, cancellation_id=case.pk)
        return case


def review_cancellation(case_id, status, actor, reason):
    if status not in ("approved", "rejected"):
        raise CheckoutError("invalid_cancellation_decision", 400)
    with transaction.atomic():
        reference = DeliveryCancellation.objects.values_list("delivery__order_id", flat=True).get(pk=case_id)
        order = Order.objects.select_for_update().get(pk=reference)
        case = DeliveryCancellation.objects.select_for_update().select_related("delivery").get(pk=case_id)
        if case.status != "requested" or order.status != "paid" or case.delivery.status not in BEFORE_SHIPPING:
            raise CheckoutError("invalid_cancellation_transition")
        case.status, case.reviewed_by, case.review_note = status, actor, reason
        case.save(update_fields=["status", "reviewed_by", "review_note", "updated_at"])
        emit(f"cancellation:{case.pk}:{status}", "cancellation.updated", order_id=order.pk, cancellation_id=case.pk, status=status)
        return case


def refund_sandbox_cancellation(case_id):
    if not sandbox_enabled():
        raise CheckoutError("provider_unavailable", 503)
    with transaction.atomic():
        reference = DeliveryCancellation.objects.values_list("delivery__order_id", flat=True).get(pk=case_id)
        order = Order.objects.select_for_update().get(pk=reference)
        case = DeliveryCancellation.objects.select_for_update().get(pk=case_id)
        if case.status == "refunded":
            return case
        delivery = OrderDelivery.objects.select_for_update().get(pk=case.delivery_id)
        if case.status != "approved" or order.status != "paid" or delivery.status not in BEFORE_SHIPPING:
            raise CheckoutError("cancellation_not_refundable")
        attempt = PaymentAttempt.objects.filter(order=order, provider="sandbox", status="captured").first()
        if attempt is None:
            raise CheckoutError("sandbox_capture_required")
        lines = list(delivery.lines.all())
        offers = {row.pk: row for row in Offer.objects.select_for_update().filter(pk__in=[line.offer_id for line in lines]).order_by("pk")}
        if any(offers[line.offer_id].available_quantity + line.quantity > 2_147_483_647 for line in lines):
            raise CheckoutError("inventory_capacity_exceeded")
        if case.amount_toman:
            record_verified_refund(attempt.pk, f"sandbox-cancellation-{case.pk}", case.amount_toman)
        for line in lines:
            offer = offers[line.offer_id]
            try:
                restock_line(offer, line, list(range(line.quantity)), f"cancellation:{case.pk}:line:{line.pk}:restock")
            except InventoryError as error:
                raise CheckoutError(error.code)
        delivery.status = "cancelled"
        delivery.save(update_fields=["status"])
        case.status = "refunded"
        case.save(update_fields=["status", "updated_at"])
        emit(f"delivery:{delivery.pk}:cancelled", "delivery.cancelled", order_id=order.pk, delivery_id=delivery.pk)
        return case
