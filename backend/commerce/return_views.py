from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .models import ReturnCase
from .returns import create_line_return
from .services import CheckoutError
from .views import _auth, _body


def case_data(case):
    return {"id": case.pk, "delivery_id": case.delivery_id, "order_id": case.delivery.order_id,
            "reason": case.reason, "status": case.status, "amount_toman": case.requested_amount_toman,
            "lines": [{"order_line_id": row.order_line_id, "quantity": row.quantity, "amount_toman": row.amount_toman, "tax_amount_toman": row.tax_amount_toman} for row in case.lines.all()]}


@require_http_methods(["GET"])
def returns(request):
    if error := _auth(request):
        return error
    rows = ReturnCase.objects.filter(requested_by=request.user).select_related("delivery").prefetch_related("lines").order_by("-pk")[:100]
    return JsonResponse({"returns": [case_data(case) for case in rows]})


@require_http_methods(["POST"])
@csrf_protect
def request_return(request, delivery_id):
    if error := _auth(request):
        return error
    data = _body(request)
    if not data or set(data) != {"line_id", "quantity", "reason"} or type(data["line_id"]) is not int:
        return JsonResponse({"error": "invalid_return"}, status=400)
    try:
        case = create_line_return(request.user, delivery_id, data["line_id"], data["quantity"], data["reason"])
    except CheckoutError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    return JsonResponse({"return": case_data(case)}, status=201)
