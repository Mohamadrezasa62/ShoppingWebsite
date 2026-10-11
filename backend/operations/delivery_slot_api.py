from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.models import ShippingRule, ShippingMethod, DeliverySlot
from commerce.shipping import booking_count
from .shipping_method_api import authorize, ROLES
from .api import _body, _reason, _audit, _error

FIELDS = {"starts_at", "ends_at", "capacity", "is_active"}


def serialize(row):
    bookings = row.booked if hasattr(row, "booked") else booking_count(row)
    history = bool(row.history_total) if hasattr(row, "history_total") else row.bookings.exists()
    return {"id": row.pk, "method_id": row.method_id, "starts_at": row.starts_at.isoformat(), "ends_at": row.ends_at.isoformat(), "capacity": row.capacity, "is_active": row.is_active, "bookings": bookings, "has_history": history}


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
        elif field == "capacity":
            if type(value) is not int or not 1 <= value <= 10000:
                raise ValueError()
        else:
            if not isinstance(value, str) or len(value) > 64:
                raise ValueError()
            value = parse_datetime(value)
            if value is None or timezone.is_naive(value):
                raise ValueError()
        setattr(row, field, value)
    row.full_clean()
    count = before.get("bookings", 0)
    if row.capacity < count or (before.get("has_history") and (row.starts_at != parse_datetime(before["starts_at"]) or row.ends_at != parse_datetime(before["ends_at"]))):
        raise ValueError()
    now = timezone.now()
    if row.is_active and not (now < row.starts_at < row.ends_at <= now + timedelta(days=90)):
        raise ValueError()
    if row.ends_at - row.starts_at > timedelta(days=1):
        raise ValueError()
    row.save()
    _audit(request, "delivery_slot_saved", "delivery_slot", row.pk, reason, before, serialize(row))


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required(*ROLES)
def slots(request, method_id):
    method = get_object_or_404(ShippingMethod, pk=method_id)
    if request.method == "GET":
        rows = method.slots.annotate(booked=Count("bookings", filter=Q(bookings__order__status__in=("pending_payment", "paid")) & ~Q(bookings__status="cancelled")), history_total=Count("bookings")).order_by("-starts_at", "-pk")[:100]
        return JsonResponse({"slots": [serialize(row) for row in rows]})
    try:
        with transaction.atomic():
            authorize(request)
            ShippingRule.objects.select_for_update().get(pk=method.rule_id)
            method = ShippingMethod.objects.select_for_update().get(pk=method.pk)
            if method.slots.filter(is_active=True, starts_at__gt=timezone.now()).count() >= 100:
                return _error("delivery_slot_limit", 409)
            row = DeliverySlot(method=method)
            save(request, row, _body(request), create=True)
    except PermissionError:
        return _error("forbidden", 403)
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_delivery_slot")
    return JsonResponse({"slot": serialize(row)}, status=201)


@require_http_methods(["PATCH"])
@csrf_protect
@staff_role_required(*ROLES)
def update(request, slot_id):
    reference = get_object_or_404(DeliverySlot.objects.select_related("method"), pk=slot_id)
    try:
        with transaction.atomic():
            authorize(request)
            ShippingRule.objects.select_for_update().get(pk=reference.method.rule_id)
            ShippingMethod.objects.select_for_update().get(pk=reference.method_id)
            row = DeliverySlot.objects.select_for_update().get(pk=reference.pk)
            save(request, row, _body(request))
    except PermissionError:
        return _error("forbidden", 403)
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_delivery_slot")
    return JsonResponse({"slot": serialize(row)})
