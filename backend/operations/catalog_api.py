from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from accounts.roles import staff_role_required
from catalog.models import Brand, Category, Product, Variant
from .api import _audit, _body, _error, _reason


def product_data(product):
    return {"id": product.pk, "title": product.title, "slug": product.slug,
            "category_id": product.category_id, "brand_id": product.brand_id,
            "description": product.description, "specifications": product.specifications,
            "status": product.status}


def apply_fields(product, data):
    fields = {"title", "slug", "description", "specifications", "category_id", "brand_id", "status", "reason"}
    if not set(data).issubset(fields):
        raise ValueError("invalid_fields")
    for key in ("title", "slug", "description", "specifications", "status"):
        if key in data:
            if key == "specifications":
                if not isinstance(data[key], dict):
                    raise ValueError("invalid_specifications")
            elif not isinstance(data[key], str):
                raise ValueError("invalid_field")
            setattr(product, key, data[key])
    for key, model in (("category_id", Category), ("brand_id", Brand)):
        if key in data:
            value = data[key]
            if key == "brand_id" and value is None:
                product.brand = None
                continue
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError("invalid_reference")
            setattr(product, key.removesuffix("_id"), get_object_or_404(model, pk=value))
    product.full_clean()


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required("catalog_operator", "marketplace_manager", "system_administrator")
def products(request):
    if request.method == "GET":
        rows = Product.objects.order_by("-created_at", "-pk")
        status = request.GET.get("status", "")
        if status:
            rows = rows.filter(status=status)
        query = request.GET.get("q", "").strip()[:120]
        if query:
            rows = rows.filter(title__icontains=query)
        try:
            page = int(request.GET.get("page", "1"))
        except ValueError:
            return _error("invalid_page")
        if not 1 <= page <= 10000:
            return _error("invalid_page")
        start = (page - 1) * 25
        items = list(rows[start:start + 26])
        return JsonResponse({"products": [product_data(row) for row in items[:25]], "page": page, "has_next": len(items) > 25})
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason:
        return _error("reason_required")
    product = Product()
    try:
        with transaction.atomic():
            apply_fields(product, data)
            product.save()
            _audit(request, "product_created", "product", product.pk, reason, {}, product_data(product))
    except (ValidationError, IntegrityError, ValueError):
        return _error("invalid_product")
    return JsonResponse({"product": product_data(product)}, status=201)


@require_http_methods(["PATCH"])
@csrf_protect
@staff_role_required("catalog_operator", "marketplace_manager", "system_administrator")
def update_product(request, product_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason:
        return _error("reason_required")
    try:
        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), pk=product_id)
            before = product_data(product)
            apply_fields(product, data)
            product.save()
            _audit(request, "product_updated", "product", product.pk, reason, before, product_data(product))
    except (ValidationError, IntegrityError, ValueError):
        return _error("invalid_product")
    return JsonResponse({"product": product_data(product)})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("catalog_operator", "marketplace_manager", "system_administrator")
def create_variant(request, product_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or not set(data).issubset({"sku", "attributes", "reason"}) or not isinstance(data.get("sku"), str) or not isinstance(data.get("attributes", {}), dict):
        return _error("invalid_variant")
    product = get_object_or_404(Product, pk=product_id)
    variant = Variant(product=product, sku=data["sku"].strip(), attributes=data.get("attributes", {}))
    try:
        with transaction.atomic():
            variant.full_clean()
            variant.save()
            _audit(request, "variant_created", "variant", variant.pk, reason, {}, {"product_id": product.pk, "sku": variant.sku, "attributes": variant.attributes})
    except (ValidationError, IntegrityError):
        return _error("invalid_variant")
    return JsonResponse({"variant": {"id": variant.pk, "sku": variant.sku, "attributes": variant.attributes}}, status=201)
