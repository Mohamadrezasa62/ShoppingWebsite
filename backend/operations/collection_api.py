from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from catalog.models import Product, ProductCollection
from .api import _audit, _body, _error, _reason


def serialize(row):
    return {"id": row.pk, "title": row.title, "slug": row.slug, "description": row.description, "published": row.is_published, "starts_at": row.starts_at.isoformat() if row.starts_at else None, "ends_at": row.ends_at.isoformat() if row.ends_at else None, "product_ids": list(row.products.values_list("pk", flat=True))}


def apply(row, data):
    if set(data) - {"reason", "title", "slug", "description", "published", "product_ids", "starts_at", "ends_at"}:
        raise ValueError()
    for key in ("title", "slug", "description"):
        if key in data:
            if not isinstance(data[key], str) or len(data[key]) > 20000:
                raise ValueError()
            setattr(row, key, data[key].strip())
    if "published" in data:
        if type(data["published"]) is not bool:
            raise ValueError()
        row.is_published = data["published"]
    for key in ("starts_at", "ends_at"):
        if key in data:
            value = data[key]
            if value is None:
                setattr(row, key, None)
            elif not isinstance(value, str):
                raise ValueError()
            else:
                date = parse_datetime(value)
                if date is None or timezone.is_naive(date):
                    raise ValueError()
                setattr(row, key, date)
    ids = data.get("product_ids")
    if ids is not None:
        if not isinstance(ids, list) or len(ids) > 50 or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids) or Product.objects.filter(pk__in=ids).count() != len(ids):
            raise ValueError()
    row.full_clean()
    row.save()
    if ids is not None:
        row.products.set(ids)


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required("catalog_operator", "marketplace_manager", "system_administrator")
def collections(request):
    if request.method == "GET":
        return JsonResponse({"collections": [serialize(row) for row in ProductCollection.objects.prefetch_related("products").order_by("-pk")[:100]]})
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason:
        return _error("reason_required")
    try:
        with transaction.atomic():
            row = ProductCollection()
            apply(row, data)
            _audit(request, "collection_created", "collection", row.pk, reason, {}, serialize(row))
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_collection")
    return JsonResponse({"collection": serialize(row)}, status=201)


@require_http_methods(["PATCH"])
@csrf_protect
@staff_role_required("catalog_operator", "marketplace_manager", "system_administrator")
def update(request, collection_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason:
        return _error("reason_required")
    try:
        with transaction.atomic():
            row = get_object_or_404(ProductCollection.objects.select_for_update(), pk=collection_id)
            before = serialize(row)
            apply(row, data)
            _audit(request, "collection_updated", "collection", row.pk, reason, before, serialize(row))
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_collection")
    return JsonResponse({"collection": serialize(row)})
