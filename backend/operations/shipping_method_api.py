from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.models import ShippingRule, ShippingMethod
from commerce.shipping import option
from .api import _body, _reason, _audit, _error

ROLES = ("marketplace_manager", "system_administrator")
FIELDS = {"code", "label", "fee_toman", "min_days", "max_days", "is_active"}


def serialize(row):
    return {**option(row), "rule_id": row.rule_id, "is_active": row.is_active}


def authorize(request):
    user = get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
    if not user.is_active or not user.is_staff or not (user.is_superuser or user.groups.filter(name__in=ROLES).exists()):
        raise PermissionError()


def save(request, row, data, create=False):
    reason = _reason(data) if data else None
    if not reason or set(data) - FIELDS - {"reason"} or (create and not FIELDS.issubset(data)):
        raise ValueError()
    before = serialize(row) if row.pk else {}
    for field in FIELDS:
        if field not in data:
            continue
        value = data[field]
        if field == "is_active":
            if type(value) is not bool:
                raise ValueError()
        elif field in ("fee_toman", "min_days", "max_days"):
            maximum = 9_000_000_000_000_000_000 if field == "fee_toman" else 365
            if type(value) is not int or not 0 <= value <= maximum:
                raise ValueError()
        elif not isinstance(value, str) or not value.strip():
            raise ValueError()
        setattr(row, field, value.strip() if isinstance(value, str) else value)
    if row.code == "standard":
        raise ValueError()
    row.full_clean()
    row.save()
    _audit(request, "shipping_method_saved", "shipping_method", row.pk, reason, before, serialize(row))


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required(*ROLES)
def methods(request, rule_id):
    rule = get_object_or_404(ShippingRule, pk=rule_id)
    if request.method == "GET":
        return JsonResponse({"methods": [serialize(row) for row in rule.methods.order_by("pk")[:20]]})
    try:
        with transaction.atomic():
            authorize(request)
            rule = ShippingRule.objects.select_for_update().get(pk=rule.pk)
            if rule.methods.count() >= 20:
                return _error("shipping_method_limit", 409)
            row = ShippingMethod(rule=rule)
            save(request, row, _body(request), create=True)
    except PermissionError:
        return _error("forbidden", 403)
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_shipping_method")
    return JsonResponse({"method": serialize(row)}, status=201)


@require_http_methods(["PATCH"])
@csrf_protect
@staff_role_required(*ROLES)
def update(request, method_id):
    reference = get_object_or_404(ShippingMethod, pk=method_id)
    try:
        with transaction.atomic():
            authorize(request)
            ShippingRule.objects.select_for_update().get(pk=reference.rule_id)
            row = ShippingMethod.objects.select_for_update().get(pk=reference.pk)
            save(request, row, _body(request))
    except PermissionError:
        return _error("forbidden", 403)
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_shipping_method")
    return JsonResponse({"method": serialize(row)})
