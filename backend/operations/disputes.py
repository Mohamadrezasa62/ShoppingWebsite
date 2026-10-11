from django.contrib.auth import get_user_model
from django.db import transaction
from commerce.models import Order, OrderDelivery
from sellers.models import Seller
from .events import emit
from .models import AuditEvent, OrderDispute

OPEN_DISPUTES = ("open", "seller_responded", "escalated")


class DisputeError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status


def text(value, limit):
    return isinstance(value, str) and "\x00" not in value and 3 <= len(value.strip()) <= limit


def lock_case(case_id):
    ref = OrderDispute.objects.filter(pk=case_id).values("delivery__seller_id", "delivery__order_id").first()
    if ref is None:
        raise DisputeError("dispute_not_found", 404)
    Seller.objects.select_for_update().get(pk=ref["delivery__seller_id"])
    Order.objects.select_for_update().get(pk=ref["delivery__order_id"])
    return OrderDispute.objects.select_for_update().get(pk=case_id)


def record(actor, case, action, reason, before):
    AuditEvent.objects.create(actor=actor, action=action, target_type="dispute", target_id=str(case.pk), reason=reason[:500], before={"status": before}, after={"status": case.status})
    emit(f"dispute:{case.pk}:{case.status}", "dispute.updated", order_id=case.delivery.order_id, dispute_id=case.pk, status=case.status)


@transaction.atomic
def open_dispute(user, delivery_id, reason):
    if not text(reason, 2000):
        raise DisputeError("invalid_dispute", 400)
    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    if not user.is_active:
        raise DisputeError("account_unavailable", 403)
    ref = OrderDelivery.objects.filter(pk=delivery_id, order__user=user).values("seller_id", "order_id").first()
    if ref is None:
        raise DisputeError("delivery_not_found", 404)
    Seller.objects.select_for_update().get(pk=ref["seller_id"])
    order = Order.objects.select_for_update().get(pk=ref["order_id"])
    delivery = OrderDelivery.objects.get(pk=delivery_id)
    existing = OrderDispute.objects.filter(delivery=delivery).first()
    if existing:
        if existing.reason != reason.strip():
            raise DisputeError("dispute_conflict")
        return existing
    if order.status != "paid" or delivery.status == "cancelled":
        raise DisputeError("dispute_not_eligible")
    case = OrderDispute.objects.create(delivery=delivery, requested_by=user, reason=reason.strip())
    record(user, case, "dispute_opened", reason.strip(), None)
    return case


@transaction.atomic
def seller_respond(actor, case_id, seller_id, body):
    if not text(body, 2000):
        raise DisputeError("invalid_response", 400)
    case = lock_case(case_id)
    if case.delivery.seller_id != seller_id or not actor.seller_memberships.filter(seller_id=seller_id).exists():
        raise DisputeError("dispute_not_found", 404)
    if case.status != "open":
        raise DisputeError("dispute_not_open")
    case.seller_response, case.status = body.strip(), "seller_responded"
    case.save(update_fields=["seller_response", "status", "updated_at"])
    record(actor, case, "dispute_seller_response", "Seller responded", "open")
    return case


@transaction.atomic
def review_dispute(actor, case_id, status, reason, resolution="", internal_note=""):
    if status not in ("escalated", "resolved", "rejected") or not text(reason, 500) or not isinstance(resolution, str) or "\x00" in resolution or len(resolution.strip()) > 1000 or not isinstance(internal_note, str) or "\x00" in internal_note or len(internal_note.strip()) > 1000:
        raise DisputeError("invalid_decision", 400)
    if status in ("resolved", "rejected") and not text(resolution, 1000):
        raise DisputeError("resolution_required", 400)
    case = lock_case(case_id)
    if case.status not in OPEN_DISPUTES or case.status == status:
        raise DisputeError("invalid_dispute_transition")
    before = case.status
    case.status, case.resolution, case.internal_note, case.reviewed_by = status, resolution.strip(), internal_note.strip(), actor
    case.save(update_fields=["status", "resolution", "internal_note", "reviewed_by", "updated_at"])
    record(actor, case, "dispute_reviewed", reason.strip(), before)
    return case
