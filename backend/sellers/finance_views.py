from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from payments.models import LedgerEntry, Settlement
from .views import _auth, _membership


@require_GET
def finance(request, seller_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    entries = LedgerEntry.objects.filter(seller_id=seller_id)
    rows = Settlement.objects.filter(seller_id=seller_id).order_by("-pk")[:100]
    return JsonResponse({"recognized_payable_toman": entries.filter(kind="seller_payable").aggregate(total=Sum("amount_toman"))["total"] or 0,
                         "commission_toman": entries.filter(kind="commission").aggregate(total=Sum("amount_toman"))["total"] or 0,
                         "unsettled_payable_toman": entries.filter(kind="seller_payable", settlement_line__isnull=True).aggregate(total=Sum("amount_toman"))["total"] or 0,
                         "settlements": [{"id": row.pk, "amount_toman": row.amount_toman, "status": row.status, "created_at": row.created_at.isoformat()} for row in rows]})


@require_GET
def performance(request, seller_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    from .reports import seller_performance
    return JsonResponse(seller_performance(seller_id))
