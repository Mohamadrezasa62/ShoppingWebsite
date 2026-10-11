import hashlib
from uuid import UUID
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.views import _auth
from operations.api import _audit, _body, _error, _reason
from .api import visible_products
from .media_processing import normalize_image
from .models import ProductReview, ReviewMedia

ROLES = ("catalog_operator", "support_agent", "system_administrator")


def data(row):
    return {"id": row.pk, "alt_text": row.alt_text, "status": row.status,
            "preview_url": f"/api/v1/catalog/review-images/{row.pk}/preview/"}


def can_moderate(user):
    return user.is_authenticated and user.is_staff and (user.is_superuser or user.groups.filter(name__in=ROLES).exists())


@require_http_methods(["GET"])
def mine(request):
    if error := _auth(request):
        return error
    rows = ProductReview.objects.filter(user=request.user).select_related("product").prefetch_related("media").order_by("-pk")[:100]
    return JsonResponse({"reviews": [{"id": row.pk, "product": row.product.title, "title": row.title, "body": row.body, "status": row.status, "images": [data(image) for image in row.media.all() if image.status != "withdrawn"]} for row in rows]})


@require_http_methods(["POST"])
@csrf_protect
def upload(request, review_id):
    if error := _auth(request):
        return error
    get_object_or_404(ProductReview, pk=review_id, user=request.user)
    alt = request.POST.get("alt_text", "").strip()
    if set(request.POST) != {"alt_text", "request_key"} or set(request.FILES) != {"image"} or "\x00" in alt or not 1 <= len(alt) <= 240:
        return _error("invalid_review_image")
    try:
        key = UUID(request.POST["request_key"])
        image = normalize_image(request.FILES["image"])
    except ValueError:
        return _error("invalid_review_image")
    digest = hashlib.sha256(image.read()).hexdigest()
    image.seek(0)
    row = None
    try:
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not user.is_active:
                return _error("account_unavailable", 403)
            review = get_object_or_404(ProductReview.objects.select_for_update(), pk=review_id, user=user)
            existing = ReviewMedia.objects.filter(review=review, request_key=key).first()
            if existing:
                if existing.digest != digest or existing.alt_text != alt:
                    return _error("review_image_conflict", 409)
                return JsonResponse({"image": data(existing)})
            if review.status == "rejected":
                return _error("review_rejected", 409)
            if ReviewMedia.objects.filter(review=review).count() >= 3:
                return _error("review_image_limit", 409)
            row = ReviewMedia(review=review, alt_text=alt, request_key=key, digest=digest)
            row.image.save(image.name, image, save=False)
            row.save()
            _audit(request, "review_image_uploaded", "review_image", row.pk, "Customer supplied review image", {}, {"review_id": review.pk, "status": row.status})
    except Exception:
        if row is not None and row.image.name:
            row.image.delete(save=False)
        raise
    return JsonResponse({"image": data(row)}, status=201)


@require_http_methods(["GET"])
def preview(request, image_id):
    if error := _auth(request):
        return error
    rows = ReviewMedia.objects.exclude(status="withdrawn")
    if not can_moderate(request.user):
        rows = rows.filter(review__user=request.user)
    row = get_object_or_404(rows, pk=image_id)
    response = FileResponse(row.image.open("rb"), content_type="image/png")
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_http_methods(["GET"])
def public(request, image_id):
    row = get_object_or_404(ReviewMedia, pk=image_id, status="approved", review__status="published", review__product_id__in=visible_products().values("pk"))
    response = FileResponse(row.image.open("rb"), content_type="image/png")
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_http_methods(["DELETE"])
@csrf_protect
def withdraw(request, image_id):
    if error := _auth(request):
        return error
    with transaction.atomic():
        row = get_object_or_404(ReviewMedia.objects.select_for_update(), pk=image_id, review__user=request.user)
        if row.status != "withdrawn":
            before = {"status": row.status}
            row.status = "withdrawn"
            row.save(update_fields=["status"])
            _audit(request, "review_image_withdrawn", "review_image", row.pk, "Customer withdrew image", before, {"status": row.status})
    return JsonResponse({"withdrawn": True})


@require_http_methods(["GET"])
@staff_role_required(*ROLES)
def queue(request):
    status = request.GET.get("status", "pending")
    if status not in ("pending", "approved", "rejected"):
        return _error("invalid_status")
    rows = ReviewMedia.objects.filter(status=status).select_related("review__product").order_by("pk")[:100]
    return JsonResponse({"images": [{**data(row), "review_id": row.review_id, "product": row.review.product.title, "review_status": row.review.status} for row in rows]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required(*ROLES)
def decision(request, image_id):
    payload = _body(request)
    reason = _reason(payload) if payload else None
    if not reason or set(payload) != {"reason", "status"} or payload["status"] not in ("pending", "approved", "rejected"):
        return _error("invalid_image_decision")
    with transaction.atomic():
        row = get_object_or_404(ReviewMedia.objects.select_for_update(), pk=image_id)
        if row.status == "withdrawn":
            return _error("image_withdrawn", 409)
        before = {"status": row.status}
        row.status = payload["status"]
        row.save(update_fields=["status"])
        _audit(request, "review_image_moderated", "review_image", row.pk, reason, before, {"status": row.status})
    return JsonResponse({"image": data(row)})
