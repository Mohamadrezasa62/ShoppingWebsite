from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .models import DeliveryCancellation
from .cancellations import request_cancellation
from .services import CheckoutError
from .views import _auth, _body


def serialize(case):
    return {"id": case.pk, "order_id": case.delivery.order_id, "delivery_id": case.delivery_id, "reason": case.reason, "amount_toman": case.amount_toman, "status": case.status, "review_note": case.review_note}


@require_http_methods(["GET"])
def cancellations(request):
    if error := _auth(request):
        return error
    return JsonResponse({"cancellations": [serialize(row) for row in DeliveryCancellation.objects.filter(requested_by=request.user).select_related("delivery").order_by("-pk")[:100]]})


@require_http_methods(["POST"])
@csrf_protect
def request_cancel(request, delivery_id):
    if error := _auth(request):
        return error
    data = _body(request)
    if not data or set(data) != {"reason"}:
        return JsonResponse({"error": "invalid_cancellation"}, status=400)
    try:
        case = request_cancellation(request.user, delivery_id, data["reason"])
    except CheckoutError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    return JsonResponse({"cancellation": serialize(case)})
