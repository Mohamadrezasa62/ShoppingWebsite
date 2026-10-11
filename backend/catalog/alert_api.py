from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from commerce.views import _auth, _body
from .models import ProductAlert
from .question_api import public_product


@require_http_methods(["GET", "POST"])
@csrf_protect
def alerts(request):
    if error := _auth(request):
        return error
    if request.method == "POST":
        data = _body(request)
        if not data or set(data) - {"product_id", "kind", "target_price_toman"} or type(data.get("product_id")) is not int or data.get("kind") not in ("price_drop", "back_in_stock"):
            return JsonResponse({"error": "invalid_alert"}, status=400)
        target = data.get("target_price_toman")
        if (data["kind"] == "price_drop" and (type(target) is not int or not 0 < target <= 9_000_000_000_000_000_000)) or (data["kind"] == "back_in_stock" and target is not None):
            return JsonResponse({"error": "invalid_alert_target"}, status=400)
        product = public_product(data["product_id"])
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            row = ProductAlert.objects.filter(user=request.user, product=product, kind=data["kind"]).first()
            if row is None and ProductAlert.objects.filter(user=request.user).count() >= 100:
                return JsonResponse({"error": "alert_limit"}, status=409)
            row, _ = ProductAlert.objects.get_or_create(user=request.user, product=product, kind=data["kind"], defaults={"target_price_toman": target})
            if not row.is_active or row.target_price_toman != target:
                row.is_active, row.target_price_toman, row.generation, row.notified_at = True, target, uuid4(), None
                row.save(update_fields=["is_active", "target_price_toman", "generation", "notified_at"])
    rows = ProductAlert.objects.filter(user=request.user).select_related("product").order_by("-pk")[:100]
    return JsonResponse({"alerts": [{"id": row.pk, "product": row.product.title, "slug": row.product.slug, "kind": row.kind, "target_price_toman": row.target_price_toman, "active": row.is_active, "notified_at": row.notified_at.isoformat() if row.notified_at else None} for row in rows]})


@require_http_methods(["DELETE"])
@csrf_protect
def delete_alert(request, alert_id):
    if error := _auth(request):
        return error
    row = get_object_or_404(ProductAlert, pk=alert_id, user=request.user)
    row.delete()
    return JsonResponse({"deleted": True})
