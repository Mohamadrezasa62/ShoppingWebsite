from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from payments.models import LedgerEntry, PaymentAttempt, Settlement
from payments.orchestration import PaymentError
from payments.settlements import approve_settlement, cancel_settlement, prepare_settlement, simulate_payout
from sellers.models import Seller
from .api import _audit, _body, _error, _reason


def settlement_data(row):
    return {"id": row.pk, "seller_id": row.seller_id, "amount_toman": row.amount_toman,
            "status": row.status, "created_by": row.created_by_id, "approved_by": row.approved_by_id,
            "created_at": row.created_at.isoformat(), "simulated": row.status == "simulated_paid"}


@require_http_methods(["GET"])
@staff_role_required("finance_operator", "system_administrator")
def transactions(request):
    entries = LedgerEntry.objects.order_by("-pk")[:100]
    attempts = PaymentAttempt.objects.order_by("-pk")[:100]
    return JsonResponse({"ledger": [{"id": row.pk, "order_id": row.order_id, "seller_id": row.seller_id, "kind": row.kind, "amount_toman": row.amount_toman} for row in entries],
                         "payments": [{"id": row.pk, "order_id": row.order_id, "provider": row.provider, "status": row.status, "amount_toman": row.amount_toman} for row in attempts]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("finance_operator", "system_administrator")
def commission(request, seller_id):
    data = _body(request)
    reason = _reason(data) if data else None
    rate = data.get("commission_bps") if data else None
    if not reason or type(rate) is not int or not 0 <= rate <= 10000:
        return _error("invalid_commission")
    with transaction.atomic():
        seller = get_object_or_404(Seller.objects.select_for_update(), pk=seller_id)
        before = {"commission_bps": seller.commission_bps}
        seller.commission_bps = rate
        seller.save(update_fields=["commission_bps"])
        _audit(request, "commission_changed", "seller", seller.pk, reason, before, {"commission_bps": rate})
    return JsonResponse({"commission_bps": rate})


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required("finance_operator", "system_administrator")
def settlements(request):
    if request.method == "GET":
        return JsonResponse({"settlements": [settlement_data(row) for row in Settlement.objects.order_by("-pk")[:100]]})
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or type(data.get("seller_id")) is not int:
        return _error("invalid_settlement")
    get_object_or_404(Seller, pk=data["seller_id"])
    try:
        with transaction.atomic():
            row = prepare_settlement(request.user, data["seller_id"], data.get("idempotency_key"))
            _audit(request, "settlement_prepared", "settlement", row.pk, reason, {}, settlement_data(row))
    except PaymentError as error:
        return _error(error.code, error.status)
    return JsonResponse({"settlement": settlement_data(row)})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("finance_operator", "system_administrator")
def settlement_action(request, settlement_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or data.get("action") not in ("approve", "simulate_payout", "cancel"):
        return _error("invalid_settlement_action")
    get_object_or_404(Settlement, pk=settlement_id)
    try:
        with transaction.atomic():
            if data["action"] == "approve":
                row = approve_settlement(request.user, settlement_id)
            elif data["action"] == "cancel":
                row = cancel_settlement(settlement_id)
            else:
                row = simulate_payout(settlement_id)
            _audit(request, data["action"], "settlement", row.pk, reason, {}, settlement_data(row))
    except PaymentError as error:
        return _error(error.code, error.status)
    return JsonResponse({"settlement": settlement_data(row)})
