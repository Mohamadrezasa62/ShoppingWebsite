import re
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.models import Coupon
from .api import _audit, _body, _error, _reason


def coupon_data(row):
    return {"id": row.pk, "code": row.code, "kind": row.kind, "value": row.value, "min_subtotal_toman": row.min_subtotal_toman,
            "max_discount_toman": row.max_discount_toman, "usage_limit": row.usage_limit, "per_user_limit": row.per_user_limit,
            "budget_toman": row.budget_toman, "budget_used_toman": getattr(row, "budget_used", None) or 0,
            "starts_at": row.starts_at.isoformat(), "ends_at": row.ends_at.isoformat(), "is_active": row.is_active}


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required("marketplace_manager", "system_administrator")
def coupons(request):
    if request.method == "GET":
        rows = Coupon.objects.annotate(budget_used=Sum("redemptions__order__discount_total_toman", filter=Q(redemptions__order__status__in=("pending_payment", "paid")))).order_by("-pk")[:100]
        return JsonResponse({"coupons": [coupon_data(row) for row in rows]})
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or not isinstance(data.get("code"), str) or not re.fullmatch(r"[A-Z0-9_-]{1,64}", data["code"].strip().upper()):
        return _error("invalid_coupon")
    values = {}
    for key in ("value", "min_subtotal_toman", "max_discount_toman", "budget_toman", "usage_limit", "per_user_limit"):
        value = data.get(key, 0 if key in ("min_subtotal_toman", "max_discount_toman", "budget_toman") else 1)
        if type(value) is not int or not 0 <= value <= 2_000_000_000:
            return _error("invalid_coupon")
        values[key] = value
    dates = {}
    for key in ("starts_at", "ends_at"):
        value = parse_datetime(data[key]) if isinstance(data.get(key), str) else None
        if value is None or timezone.is_naive(value):
            return _error("timezone_required")
        dates[key] = value
    row = Coupon(code=data["code"].strip().upper(), kind=data.get("kind"), **values, **dates)
    try:
        with transaction.atomic():
            row.full_clean()
            row.save()
            _audit(request, "coupon_created", "coupon", row.pk, reason, {}, coupon_data(row))
    except (ValidationError, IntegrityError):
        return _error("invalid_coupon")
    return JsonResponse({"coupon": coupon_data(row)}, status=201)


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("marketplace_manager", "system_administrator")
def coupon_status(request, coupon_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or type(data.get("is_active")) is not bool:
        return _error("invalid_coupon")
    with transaction.atomic():
        row = get_object_or_404(Coupon.objects.select_for_update(), pk=coupon_id)
        before = {"is_active": row.is_active}
        row.is_active = data["is_active"]
        row.save(update_fields=["is_active"])
        _audit(request, "coupon_status", "coupon", row.pk, reason, before, {"is_active": row.is_active})
        row.budget_used = row.redemptions.filter(order__status__in=("pending_payment", "paid")).aggregate(total=Sum("order__discount_total_toman"))["total"] or 0
    return JsonResponse({"coupon": coupon_data(row)})
