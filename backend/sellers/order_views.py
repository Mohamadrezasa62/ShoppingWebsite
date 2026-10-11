from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from commerce.fulfillment import FulfillmentError, transition_delivery
from commerce.models import Order, OrderDelivery
from commerce.views import delivery_data
from .models import Seller
from .views import _auth, _data, _membership


@require_http_methods(["GET"])
def deliveries(request, seller_id):
    if error := _auth(request):
        return error
    membership = _membership(request, seller_id)
    # Suspended sellers can still read already-paid obligations; cannot create offers.
    rows = OrderDelivery.objects.filter(seller_id=membership.seller_id, order__status=Order.Status.PAID).select_related("cancellation", "dispute").prefetch_related("lines").order_by("-pk")[:100]
    return JsonResponse({"deliveries": [delivery_data(row) for row in rows]})


@require_http_methods(["POST"])
@csrf_protect
def advance_delivery(request, seller_id, delivery_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    delivery = get_object_or_404(OrderDelivery, pk=delivery_id, seller_id=seller_id)
    data = _data(request)
    if not data or not set(data).issubset({"status", "tracking_code"}) or data.get("status") not in (OrderDelivery.Status.PACKING, OrderDelivery.Status.SHIPPED) or not isinstance(data.get("tracking_code", ""), str) or len(data.get("tracking_code", "")) > 120:
        return JsonResponse({"error": "invalid_delivery_update"}, status=400)
    # Delivery confirmation belongs to staff/carrier; a seller cannot self-confirm receipt.
    if delivery.fulfillment != "seller":
        return JsonResponse({"error": "platform_fulfillment_required"}, status=403)
    try:
        delivery = transition_delivery(delivery.pk, data["status"], data.get("tracking_code", ""))
    except FulfillmentError:
        return JsonResponse({"error": "invalid_transition"}, status=409)
    return JsonResponse({"delivery": delivery_data(delivery)})
