from collections import Counter
from django.db.models import Count
from django.utils import timezone
from .models import ShippingMethod, DeliverySlot, OrderDelivery


class ShippingChoiceError(Exception):
    def __init__(self, code):
        self.code = code


def group_key(seller_id, fulfillment):
    return f"{seller_id}:{fulfillment}"


def validate_choices(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 100 or any(not isinstance(key, str) or len(key) > 40 or type(identifier) is not int or not 0 <= identifier <= 9_000_000_000_000_000_000 for key, identifier in value.items()):
        raise ShippingChoiceError("invalid_shipping_methods")
    return value


def option(row, standard=False):
    return {"id": 0 if standard else row.pk, "code": "standard" if standard else row.code,
            "label": "ارسال معمولی" if standard else row.label, "fee_toman": row.fee_toman,
            "min_days": row.min_days, "max_days": row.max_days}


def resolve_choices(groups, rules, choices, *, lock=False):
    choices = validate_choices(choices)
    keys = {group_key(*group) for group in groups}
    if set(choices) - keys:
        raise ShippingChoiceError("invalid_shipping_methods")
    queryset = ShippingMethod.objects.filter(rule_id__in=[rule.pk for rule in rules.values()], is_active=True).order_by("pk")
    if lock:
        queryset = queryset.filter(pk__in=[identifier for identifier in choices.values() if identifier]).select_for_update()
    methods = list(queryset)
    selected, options = {}, {}
    for seller_id, fulfillment in groups:
        key = group_key(seller_id, fulfillment)
        rule = rules.get(fulfillment)
        if rule is None:
            continue
        options[key] = [option(rule, True)] + [option(method) for method in methods if method.rule_id == rule.pk]
        identifier = choices.get(key, 0)
        selected[key] = next((item for item in options[key] if item["id"] == identifier), None)
        if selected[key] is None:
            raise ShippingChoiceError("shipping_method_unavailable")
    return selected, options


def booking_count(slot):
    return slot.bookings.filter(order__status__in=("pending_payment", "paid")).exclude(status="cancelled").count()


def resolve_slots(selected, choices, *, lock=False):
    try:
        choices = validate_choices(choices)
    except ShippingChoiceError:
        raise ShippingChoiceError("invalid_shipping_slots")
    if set(choices) - set(selected):
        raise ShippingChoiceError("invalid_shipping_slots")
    query = DeliverySlot.objects.filter(method_id__in=[item["id"] for item in selected.values() if item["id"]], is_active=True, starts_at__gt=timezone.now()).order_by("pk")
    if lock:
        query = query.filter(pk__in=[identifier for identifier in choices.values() if identifier]).select_for_update()
    slots = list(query)
    counts = dict(OrderDelivery.objects.filter(shipping_slot_id__in=[slot.pk for slot in slots], order__status__in=("pending_payment", "paid")).exclude(status="cancelled").values("shipping_slot_id").annotate(total=Count("pk")).values_list("shipping_slot_id", "total"))
    by_method = {}
    for slot in slots:
        free = max(0, slot.capacity - counts.get(slot.pk, 0))
        if free:
            by_method.setdefault(slot.method_id, []).append({"id": slot.pk, "starts_at": slot.starts_at.isoformat(), "ends_at": slot.ends_at.isoformat(), "remaining": free})
    requested = Counter(identifier for identifier in choices.values() if identifier)
    available, resolved = {}, {}
    for key, method in selected.items():
        windows = by_method.get(method["id"], [])
        available[key] = sorted(windows, key=lambda item: (item["starts_at"], item["id"]))[:100]
        identifier = choices.get(key, 0)
        if identifier:
            chosen = next((window for window in windows if window["id"] == identifier), None)
            if chosen is None or chosen["remaining"] < requested[identifier]:
                raise ShippingChoiceError("shipping_slot_unavailable")
            resolved[key] = {field: chosen[field] for field in ("id", "starts_at", "ends_at")}
        else:
            resolved[key] = None
    return resolved, available
