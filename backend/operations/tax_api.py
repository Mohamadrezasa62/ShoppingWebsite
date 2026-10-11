from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from catalog.models import Category
from commerce.models import TaxRule
from .api import _body, _reason, _audit, _error
from .shipping_method_api import ROLES, authorize


def serialize(row):
    return {"category_id": row.category_id, "label": row.label, "rate_bps": row.rate_bps, "is_active": row.is_active}


@require_http_methods(["GET", "PUT"])
@csrf_protect
@staff_role_required(*ROLES)
def rule(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if request.method == "GET":
        row = TaxRule.objects.filter(category=category).first()
        return JsonResponse({"rule": serialize(row) if row else {"category_id": category.pk, "label": "", "rate_bps": 0, "is_active": False}})
    data = _body(request)
    if not data or set(data) != {"label", "rate_bps", "is_active", "reason"} or not _reason(data):
        return _error("invalid_tax_rule")
    if (not isinstance(data["label"], str) or not 1 <= len(data["label"].strip()) <= 160
            or type(data["rate_bps"]) is not int or not 0 <= data["rate_bps"] <= 10000
            or type(data["is_active"]) is not bool):
        return _error("invalid_tax_rule")
    try:
        with transaction.atomic():
            authorize(request)
            Category.objects.select_for_update().get(pk=category.pk)
            row = TaxRule.objects.filter(category=category).first()
            before = serialize(row) if row else {}
            row = row or TaxRule(category=category)
            row.label, row.rate_bps, row.is_active = data["label"].strip(), data["rate_bps"], data["is_active"]
            row.full_clean()
            row.save()
            _audit(request, "tax_rule_saved", "category_tax_rule", row.pk, _reason(data), before, serialize(row))
    except PermissionError:
        return _error("forbidden", 403)
    except ValidationError:
        return _error("invalid_tax_rule")
    return JsonResponse({"rule": serialize(row)})
