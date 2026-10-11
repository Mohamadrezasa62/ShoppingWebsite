from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from catalog.models import ProductReview
from .api import _audit, _body, _error, _reason


@require_http_methods(["GET"])
@staff_role_required("catalog_operator", "support_agent", "system_administrator")
def reviews(request):
    rows = ProductReview.objects.select_related("product").order_by("-pk")
    if status := request.GET.get("status", "pending"):
        rows = rows.filter(status=status)
    return JsonResponse({"reviews": [{"id": row.pk, "product": row.product.title, "rating": row.rating, "title": row.title, "body": row.body, "status": row.status} for row in rows[:100]]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("catalog_operator", "support_agent", "system_administrator")
def moderate_review(request, review_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or data.get("status") not in ("published", "rejected", "pending"):
        return _error("invalid_review_decision")
    with transaction.atomic():
        review = get_object_or_404(ProductReview.objects.select_for_update(), pk=review_id)
        before = {"status": review.status}
        review.status = data["status"]
        review.save(update_fields=["status"])
        _audit(request, "review_moderated", "review", review.pk, reason, before, {"status": review.status})
    return JsonResponse({"status": review.status})
