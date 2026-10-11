from django.utils import timezone
from django.db.models import Sum


def coupon_discount(coupon, subtotal, user):
    if coupon is None:
        return 0
    now = timezone.now()
    if not coupon.is_active or not coupon.starts_at <= now < coupon.ends_at or subtotal < coupon.min_subtotal_toman:
        raise ValueError("coupon_not_eligible")
    # Pending orders reserve coupon capacity; expiration/cancellation releases it.
    active = coupon.redemptions.filter(order__status__in=("pending_payment", "paid"))
    if active.count() >= coupon.usage_limit or active.filter(user=user).count() >= coupon.per_user_limit:
        raise ValueError("coupon_usage_exceeded")
    amount = subtotal * coupon.value // 100 if coupon.kind == "percent" else coupon.value
    if coupon.max_discount_toman:
        amount = min(amount, coupon.max_discount_toman)
    amount = min(subtotal, amount)
    if coupon.budget_toman:
        used = active.aggregate(total=Sum("order__discount_total_toman"))["total"] or 0
        if used + amount > coupon.budget_toman:
            raise ValueError("coupon_budget_exceeded")
    return amount


def allocate_discount(amounts, discount):
    """Largest remainder with a stable tie break; sum equals the order discount."""
    total = sum(amounts)
    if total == 0:
        return [0] * len(amounts)
    allocations = [amount * discount // total for amount in amounts]
    remaining = discount - sum(allocations)
    ranked = sorted(range(len(amounts)), key=lambda index: (-(amounts[index] * discount % total), index))
    for index in ranked[:remaining]:
        allocations[index] += 1
    return allocations
