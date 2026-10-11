from django.db import IntegrityError, transaction
from django.db.models import Avg, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from commerce.views import _auth, _body
from .models import Product, ProductReview, ReviewMedia, WishlistItem
from .api import visible_products
from .trust import ReviewError, add_wishlist_item, submit_review


@require_http_methods(["GET", "POST"])
@csrf_protect
def wishlist(request):
    if error := _auth(request):
        return error
    if request.method == "POST":
        data = _body(request)
        if not data or set(data) != {"product_id"} or type(data["product_id"]) is not int:
            return JsonResponse({"error": "invalid_product"}, status=400)
        product = get_object_or_404(visible_products(), pk=data["product_id"])
        add_wishlist_item(request.user, product)
    rows = WishlistItem.objects.filter(user=request.user).select_related("product").order_by("-created_at")[:100]
    return JsonResponse({"items": [{"product_id": row.product_id, "title": row.product.title, "slug": row.product.slug, "available": row.product.status == "published"} for row in rows]})


@require_http_methods(["DELETE"])
@csrf_protect
def remove_wishlist(request, product_id):
    if error := _auth(request):
        return error
    WishlistItem.objects.filter(user=request.user, product_id=product_id).delete()
    return JsonResponse({"deleted": True})


@require_http_methods(["GET", "POST"])
@csrf_protect
def reviews(request, product_id):
    product = get_object_or_404(visible_products(), pk=product_id)
    if request.method == "POST":
        if error := _auth(request):
            return error
        data = _body(request)
        if not data or set(data) != {"rating", "title", "body"}:
            return JsonResponse({"error": "invalid_review"}, status=400)
        try:
            with transaction.atomic():
                review = submit_review(request.user, product, data["rating"], data["title"], data["body"])
        except (ReviewError, IntegrityError):
            return JsonResponse({"error": "review_not_eligible"}, status=409)
        return JsonResponse({"review": {"id": review.pk, "status": review.status}}, status=201)
    rows = ProductReview.objects.filter(product=product, status="published").prefetch_related(Prefetch("media", queryset=ReviewMedia.objects.filter(status="approved").order_by("pk"), to_attr="approved_media")).order_by("-created_at")
    return JsonResponse({"average_rating": rows.aggregate(value=Avg("rating"))["value"], "count": rows.count(), "reviews": [{"id": row.pk, "rating": row.rating, "title": row.title, "body": row.body, "verified_purchase": row.verified_purchase, "images": [{"url": f"/api/v1/catalog/review-images/{image.pk}/", "alt": image.alt_text} for image in row.approved_media]} for row in rows[:50]]})
