from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.views import _auth
from sellers.views import _membership
from .api import _body, _error
from .models import OrderDispute
from .disputes import DisputeError, open_dispute, seller_respond, review_dispute


def serialize(row, internal=False):
    return {"id": row.pk, "delivery_id": row.delivery_id, "order_id": row.delivery.order_id, "seller": row.delivery.seller_name, "status": row.status, "reason": row.reason, "seller_response": row.seller_response, "resolution": row.resolution, **({"internal_note": row.internal_note} if internal else {})}


@require_http_methods(["GET", "POST"])
@csrf_protect
def mine(request):
    if error := _auth(request):
        return error
    if request.method == "POST":
        data = _body(request)
        if not data or set(data) != {"delivery_id", "reason"} or type(data["delivery_id"]) is not int:
            return _error("invalid_dispute")
        try:
            case = open_dispute(request.user, data["delivery_id"], data["reason"])
        except DisputeError as exc:
            return _error(exc.code, exc.status)
        return JsonResponse({"dispute": serialize(case)})
    rows = OrderDispute.objects.filter(requested_by=request.user).select_related("delivery").order_by("-pk")[:100]
    return JsonResponse({"disputes": [serialize(row) for row in rows]})


@require_http_methods(["GET"])
@staff_role_required("support_agent", "marketplace_manager", "system_administrator")
def queue(request):
    rows = OrderDispute.objects.select_related("delivery").order_by("-pk")[:100]
    return JsonResponse({"disputes": [serialize(row, True) for row in rows]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("marketplace_manager", "system_administrator")
def decision(request, case_id):
    data = _body(request)
    if not data or set(data) != {"status", "reason", "resolution", "internal_note"}:
        return _error("invalid_decision")
    try:
        case = review_dispute(request.user, case_id, **data)
    except DisputeError as exc:
        return _error(exc.code, exc.status)
    return JsonResponse({"dispute": serialize(case, True)})


@require_http_methods(["GET", "POST"])
@csrf_protect
def seller_cases(request, seller_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    if request.method == "POST":
        data = _body(request)
        if not data or set(data) != {"dispute_id", "body"} or type(data["dispute_id"]) is not int:
            return _error("invalid_response")
        get_object_or_404(OrderDispute, pk=data["dispute_id"], delivery__seller_id=seller_id)
        try:
            case = seller_respond(request.user, data["dispute_id"], seller_id, data["body"])
        except DisputeError as exc:
            return _error(exc.code, exc.status)
        return JsonResponse({"dispute": serialize(case)})
    rows = OrderDispute.objects.filter(delivery__seller_id=seller_id).select_related("delivery").order_by("-pk")[:100]
    return JsonResponse({"disputes": [serialize(row) for row in rows]})
