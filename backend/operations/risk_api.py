from uuid import UUID
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.models import Order
from .api import _body, _error, _reason, _audit
from .models import OrderRiskCase

READ_ROLES = ("support_agent", "finance_operator", "marketplace_manager", "system_administrator")
WRITE_ROLES = ("marketplace_manager", "system_administrator")


def can_write(user):
    return user.is_active and user.is_staff and (user.is_superuser or user.groups.filter(name__in=WRITE_ROLES).exists())


def serialize(row):
    return {"id": row.pk, "order_id": row.order_id, "category": row.category, "severity": row.severity, "description": row.description, "hold_fulfillment": row.hold_fulfillment, "status": row.status, "outcome": row.outcome, "resolution": row.resolution, "created_at": row.created_at.isoformat()}


@require_http_methods(["GET"])
@staff_role_required(*READ_ROLES)
def queue(request):
    status = request.GET.get("status", "open")
    if status not in ("open", "escalated", "cleared"):
        return _error("invalid_status")
    rows = OrderRiskCase.objects.filter(status=status).order_by("-pk")[:100]
    return JsonResponse({"cases": [serialize(row) for row in rows]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required(*WRITE_ROLES)
def create(request):
    data = _body(request)
    reason = _reason(data) if data else None
    fields = {"order_id", "request_key", "category", "severity", "description", "hold_fulfillment", "reason"}
    if not reason or set(data) != fields or type(data["order_id"]) is not int or type(data["hold_fulfillment"]) is not bool or data["category"] not in ("payment_abuse", "account_takeover", "delivery_abuse", "other") or data["severity"] not in ("low", "medium", "high") or not isinstance(data["description"], str) or "\x00" in data["description"] or not 3 <= len(data["description"].strip()) <= 2000:
        return _error("invalid_risk_case")
    try:
        key = UUID(str(data["request_key"]))
    except (ValueError, TypeError, AttributeError):
        return _error("invalid_request_key")
    with transaction.atomic():
        actor = get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
        if not can_write(actor):
            return _error("forbidden", 403)
        order = get_object_or_404(Order.objects.select_for_update(), pk=data["order_id"])
        existing = OrderRiskCase.objects.filter(opened_by=actor, request_key=key).first()
        if existing:
            matches = existing.order_id == order.pk and all(getattr(existing, field) == data[field] for field in ("category", "severity", "hold_fulfillment")) and existing.description == data["description"].strip()
            if not matches:
                return _error("risk_idempotency_conflict", 409)
            return JsonResponse({"case": serialize(existing)})
        if order.status not in ("paid", "pending_payment") or (data["hold_fulfillment"] and not order.deliveries.filter(status__in=("awaiting_fulfillment", "packing")).exists()):
            return _error("risk_case_not_eligible", 409)
        if order.risk_cases.exclude(status="cleared").count() >= 10:
            return _error("risk_case_limit", 409)
        row = OrderRiskCase.objects.create(order=order, opened_by=actor, request_key=key, category=data["category"], severity=data["severity"], description=data["description"].strip(), hold_fulfillment=data["hold_fulfillment"])
        _audit(request, "risk_case_opened", "risk_case", row.pk, reason, {}, {"order_id": order.pk, "status": row.status, "hold_fulfillment": row.hold_fulfillment})
    return JsonResponse({"case": serialize(row)}, status=201)


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required(*WRITE_ROLES)
def decision(request, case_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"action", "outcome", "resolution", "reason"} or data["action"] not in ("escalate", "clear") or not isinstance(data["resolution"], str) or "\x00" in data["resolution"] or not 3 <= len(data["resolution"].strip()) <= 1000 or (data["action"] == "clear" and data["outcome"] not in ("dismissed", "confirmed")) or (data["action"] == "escalate" and data["outcome"] != ""):
        return _error("invalid_risk_decision")
    with transaction.atomic():
        order_id = get_object_or_404(OrderRiskCase, pk=case_id).order_id
        Order.objects.select_for_update().get(pk=order_id)
        row = OrderRiskCase.objects.select_for_update().get(pk=case_id)
        if row.status == "cleared" or (data["action"] == "escalate" and row.status == "escalated"):
            return _error("invalid_risk_transition", 409)
        before = {"status": row.status}
        row.status = "escalated" if data["action"] == "escalate" else "cleared"
        row.outcome, row.resolution, row.reviewed_by = data["outcome"], data["resolution"].strip(), request.user
        row.save(update_fields=["status", "outcome", "resolution", "reviewed_by", "updated_at"])
        _audit(request, "risk_case_reviewed", "risk_case", row.pk, reason, before, {"status": row.status, "outcome": row.outcome})
    return JsonResponse({"case": serialize(row)})
