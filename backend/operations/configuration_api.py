from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from catalog.models import Brand, Category, CategoryFacet
from commerce.models import ShippingRule
from .api import _audit, _body, _error, _reason

CATALOG_ROLES = ("catalog_operator", "marketplace_manager", "system_administrator")
SHIPPING_ROLES = ("marketplace_manager", "system_administrator")


def serialize(row, fields):
    return {"id": row.pk, **{field: getattr(row, field) for field in fields}}


def save(request, row, data, fields, kind):
    reason = _reason(data) if data else None
    if not reason or set(data) - set(fields) - {"reason"}:
        raise ValueError()
    before = serialize(row, fields) if row.pk else {}
    for key in fields:
        if key not in data:
            continue
        value = data[key]
        if key == "is_active":
            if type(value) is not bool:
                raise ValueError()
        elif key in ("fee_toman", "min_days", "max_days", "position"):
            maximum = 9_000_000_000_000_000_000 if key == "fee_toman" else 1000 if key == "position" else 365
            if type(value) is not int or not 0 <= value <= maximum:
                raise ValueError()
        elif key == "choices":
            if not isinstance(value, list) or len(value) > 100:
                raise ValueError()
        elif not isinstance(value, str):
            raise ValueError()
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    row.full_clean()
    row.save()
    _audit(request, f"{kind}_saved", kind, row.pk, reason, before, serialize(row, fields))


BRAND_FIELDS = ("name", "slug", "is_active")
FACET_FIELDS = ("key", "label", "choices", "position", "is_active")
SHIPPING_FIELDS = ("province", "fulfillment", "fee_toman", "min_days", "max_days", "is_active")


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required(*CATALOG_ROLES)
def brands(request):
    if request.method == "GET":
        rows = Brand.objects.order_by("name")[:500]
        return JsonResponse({"brands": [serialize(row, BRAND_FIELDS) for row in rows]})
    try:
        with transaction.atomic():
            row = Brand()
            save(request, row, _body(request), BRAND_FIELDS, "brand")
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_brand")
    return JsonResponse({"brand": serialize(row, BRAND_FIELDS)}, status=201)


@require_http_methods(["PATCH"])
@csrf_protect
@staff_role_required(*CATALOG_ROLES)
def brand(request, brand_id):
    try:
        with transaction.atomic():
            row = get_object_or_404(Brand.objects.select_for_update(), pk=brand_id)
            save(request, row, _body(request), BRAND_FIELDS, "brand")
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_brand")
    return JsonResponse({"brand": serialize(row, BRAND_FIELDS)})


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required(*CATALOG_ROLES)
def facets(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if request.method == "GET":
        return JsonResponse({"facets": [serialize(row, FACET_FIELDS) for row in category.facets.all()[:100]]})
    try:
        with transaction.atomic():
            Category.objects.select_for_update().get(pk=category_id)
            row = CategoryFacet(category=category)
            save(request, row, _body(request), FACET_FIELDS, "facet")
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_facet")
    return JsonResponse({"facet": serialize(row, FACET_FIELDS)}, status=201)


@require_http_methods(["PATCH"])
@csrf_protect
@staff_role_required(*CATALOG_ROLES)
def facet(request, facet_id):
    try:
        with transaction.atomic():
            row = get_object_or_404(CategoryFacet.objects.select_for_update(), pk=facet_id)
            save(request, row, _body(request), FACET_FIELDS, "facet")
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_facet")
    return JsonResponse({"facet": serialize(row, FACET_FIELDS)})


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required(*SHIPPING_ROLES)
def shipping_rules(request):
    if request.method == "GET":
        return JsonResponse({"shipping_rules": [serialize(row, SHIPPING_FIELDS) for row in ShippingRule.objects.order_by("province", "fulfillment")[:500]]})
    try:
        with transaction.atomic():
            row = ShippingRule()
            save(request, row, _body(request), SHIPPING_FIELDS, "shipping_rule")
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_shipping_rule")
    return JsonResponse({"shipping_rule": serialize(row, SHIPPING_FIELDS)}, status=201)


@require_http_methods(["PATCH"])
@csrf_protect
@staff_role_required(*SHIPPING_ROLES)
def shipping_rule(request, rule_id):
    try:
        with transaction.atomic():
            row = get_object_or_404(ShippingRule.objects.select_for_update(), pk=rule_id)
            save(request, row, _body(request), SHIPPING_FIELDS, "shipping_rule")
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_shipping_rule")
    return JsonResponse({"shipping_rule": serialize(row, SHIPPING_FIELDS)})
