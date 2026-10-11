from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from catalog.models import Product, ProductMedia
from catalog.media_processing import normalize_image
from .api import _audit, _body, _error, _reason

ROLES = ("catalog_operator", "marketplace_manager", "system_administrator")


def media_data(row):
    return {"id": row.pk, "alt_text": row.alt_text, "position": row.position, "approved": row.is_approved, "preview_url": f"/api/v1/operations/media/{row.pk}/preview/"}


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required(*ROLES)
def media(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if request.method == "POST":
        reason = _reason(request.POST)
        alt = request.POST.get("alt_text", "").strip()
        if not reason or not 1 <= len(alt) <= 240 or set(request.FILES) != {"image"}:
            return _error("invalid_media")
        try:
            image = normalize_image(request.FILES.get("image"))
        except ValueError as error:
            return _error(str(error))
        row = ProductMedia(product=product, alt_text=alt)
        try:
            with transaction.atomic():
                Product.objects.select_for_update().get(pk=product.pk)
                if ProductMedia.objects.filter(product=product).count() >= 20:
                    return _error("media_limit", 409)
                row.image.save(image.name, image, save=False)
                row.save()
                _audit(request, "product_media_uploaded", "media", row.pk, reason, {}, {"product_id": product.pk, "approved": False})
        except Exception:
            if row.image.name:
                row.image.delete(save=False)
            raise
        return JsonResponse({"media": media_data(row)}, status=201)
    return JsonResponse({"media": [media_data(row) for row in product.media.all()]})


@require_http_methods(["GET"])
@staff_role_required(*ROLES)
def preview(request, media_id):
    row = get_object_or_404(ProductMedia, pk=media_id)
    response = FileResponse(row.image.open("rb"), content_type="image/png")
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_http_methods(["PATCH"])
@csrf_protect
@staff_role_required(*ROLES)
def decision(request, media_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) - {"reason", "approved", "position", "alt_text"} or ("approved" in data and type(data["approved"]) is not bool) or ("position" in data and (type(data["position"]) is not int or not 0 <= data["position"] <= 1000)) or ("alt_text" in data and (not isinstance(data["alt_text"], str) or not 1 <= len(data["alt_text"].strip()) <= 240)):
        return _error("invalid_media_decision")
    with transaction.atomic():
        row = get_object_or_404(ProductMedia.objects.select_for_update(), pk=media_id)
        before = {"approved": row.is_approved, "position": row.position, "alt_text": row.alt_text}
        if "approved" in data:
            row.is_approved = data["approved"]
        if "position" in data:
            row.position = data["position"]
        if "alt_text" in data:
            row.alt_text = data["alt_text"].strip()
        row.save(update_fields=["is_approved", "position", "alt_text"])
        _audit(request, "product_media_reviewed", "media", row.pk, reason, before, {"approved": row.is_approved, "position": row.position, "alt_text": row.alt_text})
    return JsonResponse({"media": media_data(row)})
