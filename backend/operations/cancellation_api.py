from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.models import DeliveryCancellation
from commerce.cancellations import review_cancellation, refund_sandbox_cancellation
from commerce.cancellation_views import serialize
from commerce.services import CheckoutError
from .api import _audit, _body, _error, _reason


@require_http_methods(["GET"])
@staff_role_required("support_agent", "finance_operator", "marketplace_manager", "system_administrator")
def cancellations(request):
    rows = DeliveryCancellation.objects.select_related("delivery").order_by("-pk")[:100]
    return JsonResponse({"cancellations": [serialize(row) for row in rows]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("marketplace_manager", "system_administrator")
def decision(request, case_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"reason", "status"}:
        return _error("invalid_cancellation_decision")
    get_object_or_404(DeliveryCancellation, pk=case_id)
    try:
        with transaction.atomic():
            case = review_cancellation(case_id, data["status"], request.user, reason)
            _audit(request, "cancellation_reviewed", "cancellation", case.pk, reason, {"status": "requested"}, {"status": case.status})
    except CheckoutError as error:
        return _error(error.code, error.status)
    return JsonResponse({"cancellation": serialize(case)})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("finance_operator", "system_administrator")
def refund(request, case_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"reason"}:
        return _error("reason_required")
    get_object_or_404(DeliveryCancellation, pk=case_id)
    try:
        with transaction.atomic():
            case = refund_sandbox_cancellation(case_id)
            _audit(request, "cancellation_sandbox_refunded", "cancellation", case.pk, reason, {}, {"status": case.status})
    except (CheckoutError, ValueError) as error:
        return _error(error.code if isinstance(error, CheckoutError) else "refund_limit_exceeded", error.status if isinstance(error, CheckoutError) else 409)
    return JsonResponse({"cancellation": serialize(case)})
