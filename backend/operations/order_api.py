from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.fulfillment import FulfillmentError, transition_delivery
from commerce.models import Order, OrderDelivery
from commerce.views import _order_data, delivery_data
from .api import _audit, _body, _error, _reason


@require_http_methods(["GET"])
@staff_role_required("support_agent", "marketplace_manager", "system_administrator")
def orders(request):
    rows = Order.objects.order_by("-created_at", "-pk")
    if status := request.GET.get("status"):
        rows = rows.filter(status=status)
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        return _error("invalid_page")
    if not 1 <= page <= 10000:
        return _error("invalid_page")
    rows = list(rows[(page - 1) * 25:page * 25 + 1])
    return JsonResponse({"orders": [{"id": row.pk, "status": row.status,
                         "grand_total_toman": row.grand_total_toman,
                         "created_at": row.created_at.isoformat()} for row in rows[:25]],
                         "page": page, "has_next": len(rows) > 25})


@require_http_methods(["GET"])
@staff_role_required("support_agent", "marketplace_manager", "system_administrator")
def order_detail(request, order_id):
    return JsonResponse({"order": _order_data(get_object_or_404(Order, pk=order_id))})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("marketplace_manager", "system_administrator")
def advance_delivery(request, delivery_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or not set(data).issubset({"status", "tracking_code", "reason"}) or data.get("status") not in ("packing", "shipped", "delivered") or not isinstance(data.get("tracking_code", ""), str) or len(data.get("tracking_code", "")) > 120:
        return _error("invalid_delivery_update")
    try:
        with transaction.atomic():
            reference = get_object_or_404(OrderDelivery, pk=delivery_id)
            Order.objects.select_for_update().get(pk=reference.order_id)
            delivery = get_object_or_404(OrderDelivery.objects.select_for_update(), pk=delivery_id)
            before = {"status": delivery.status, "tracking_code": delivery.tracking_code}
            delivery = transition_delivery(delivery.pk, data["status"], data.get("tracking_code", ""))
            _audit(request, "delivery_transition", "delivery", delivery.pk, reason,
                   before, {"status": delivery.status, "tracking_code": delivery.tracking_code})
    except FulfillmentError:
        return _error("invalid_transition", 409)
    return JsonResponse({"delivery": delivery_data(delivery)})
