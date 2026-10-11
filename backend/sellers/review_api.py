from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.models import OrderDelivery
from commerce.views import _auth
from operations.api import _body, _error, _reason, _audit
from .models import Seller, SellerReview

ROLES = ("support_agent", "marketplace_manager", "system_administrator")


@require_http_methods(["GET"])
def public(request, seller_id):
    seller = get_object_or_404(Seller, pk=seller_id, status="approved")
    rows = SellerReview.objects.filter(seller=seller, status="published").order_by("-pk")
    summary = rows.aggregate(average_rating=Avg("rating"), count=Count("pk"))
    return JsonResponse({"seller": {"id": seller.pk, "name": seller.name}, **summary,
                         "reviews": [{"rating": row.rating, "body": row.body, "verified_purchase": True} for row in rows[:50]]})


@require_http_methods(["GET", "POST"])
@csrf_protect
def mine(request):
    if error := _auth(request):
        return error
    if request.method == "POST":
        data = _body(request)
        if not data or set(data) != {"delivery_id", "rating", "body"} or type(data["delivery_id"]) is not int or type(data["rating"]) is not int or not 1 <= data["rating"] <= 5 or not isinstance(data["body"], str) or "\x00" in data["body"] or not 3 <= len(data["body"].strip()) <= 2000:
            return _error("invalid_seller_review")
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not user.is_active:
                return _error("account_unavailable", 403)
            delivery = get_object_or_404(OrderDelivery.objects.select_for_update(of=("self",)).select_related("order"), pk=data["delivery_id"], order__user=user)
            existing = SellerReview.objects.filter(delivery=delivery).first()
            if existing:
                if existing.rating != data["rating"] or existing.body != data["body"].strip():
                    return _error("seller_review_conflict", 409)
                return JsonResponse({"review": {"id": existing.pk, "status": existing.status}})
            if delivery.status != "delivered" or delivery.order.status != "paid" or user.seller_memberships.filter(seller_id=delivery.seller_id).exists():
                return _error("seller_review_not_eligible", 409)
            row = SellerReview.objects.create(delivery=delivery, seller_id=delivery.seller_id, user=user, rating=data["rating"], body=data["body"].strip())
        return JsonResponse({"review": {"id": row.pk, "status": row.status}}, status=201)
    rows = SellerReview.objects.filter(user=request.user).select_related("seller").order_by("-pk")[:100]
    return JsonResponse({"reviews": [{"id": row.pk, "delivery_id": row.delivery_id, "seller": row.seller.name, "rating": row.rating, "body": row.body, "status": row.status} for row in rows]})


@require_http_methods(["GET"])
@staff_role_required(*ROLES)
def queue(request):
    status = request.GET.get("status", "pending")
    if status not in ("pending", "published", "rejected"):
        return _error("invalid_status")
    rows = SellerReview.objects.filter(status=status).select_related("seller").order_by("pk")[:100]
    return JsonResponse({"reviews": [{"id": row.pk, "seller": row.seller.name, "rating": row.rating, "body": row.body, "status": row.status} for row in rows]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required(*ROLES)
def decision(request, review_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"reason", "status"} or data["status"] not in ("pending", "published", "rejected"):
        return _error("invalid_review_decision")
    with transaction.atomic():
        row = get_object_or_404(SellerReview.objects.select_for_update(), pk=review_id)
        before = {"status": row.status}
        row.status = data["status"]
        row.save(update_fields=["status"])
        _audit(request, "seller_review_moderated", "seller_review", row.pk, reason, before, {"status": row.status})
    return JsonResponse({"status": row.status})
