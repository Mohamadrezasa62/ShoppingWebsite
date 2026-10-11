from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.models import ReturnCase
from commerce.return_views import case_data
from commerce.returns import refund_sandbox_return, transition_return
from commerce.services import CheckoutError
from .api import _audit, _body, _error, _reason


@require_http_methods(["GET"])
@staff_role_required("support_agent", "finance_operator", "marketplace_manager", "system_administrator")
def returns(request):
    rows = ReturnCase.objects.select_related("delivery").prefetch_related("lines").order_by("-pk")[:100]
    return JsonResponse({"returns": [case_data(case) for case in rows]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("support_agent", "marketplace_manager", "system_administrator")
def decision(request, case_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or data.get("status") not in ("approved", "rejected", "received", "refund_pending") or type(data.get("restock", False)) is not bool:
        return _error("invalid_return_decision")
    get_object_or_404(ReturnCase, pk=case_id)
    try:
        with transaction.atomic():
            case = transition_return(case_id, data["status"], data.get("restock", False))
            _audit(request, "return_transition", "return", case.pk, reason, {}, {"status": case.status})
    except CheckoutError as error:
        return _error(error.code, error.status)
    return JsonResponse({"return": case_data(case)})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("finance_operator", "system_administrator")
def sandbox_refund(request, case_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason:
        return _error("reason_required")
    get_object_or_404(ReturnCase, pk=case_id)
    try:
        with transaction.atomic():
            case = refund_sandbox_return(case_id)
            _audit(request, "sandbox_return_refund", "return", case.pk, reason, {}, {"status": case.status})
    except (CheckoutError, ValueError) as error:
        return _error(error.code if isinstance(error, CheckoutError) else "refund_limit_exceeded", error.status if isinstance(error, CheckoutError) else 409)
    return JsonResponse({"return": case_data(case)})
