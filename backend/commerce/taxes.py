"""Explicit, exclusive category tax configuration; no jurisdiction rate is assumed."""
from catalog.models import Category
from .models import TaxRule
from .promotions import allocate_discount


def calculate_taxes(lines, offers, discount, *, lock=False):
    category_ids = sorted({offer.variant.product.category_id for offer in offers.values()})
    if lock:
        # Lock parents even when no rule exists, serializing first-time rule creation.
        categories = {category.pk: category for category in Category.objects.select_for_update().filter(pk__in=category_ids).order_by("pk")}
        for offer in offers.values():
            offer.variant.product.category = categories[offer.variant.product.category_id]
    rules = {rule.category_id: rule for rule in TaxRule.objects.filter(category_id__in=category_ids, is_active=True)}
    amounts = [offers[line.offer_id].price_toman * line.quantity for line in lines]
    discounts = allocate_discount(amounts, discount)
    result = []
    for line, amount, reduction in zip(lines, amounts, discounts):
        rule = rules.get(offers[line.offer_id].variant.product.category_id)
        rate = rule.rate_bps if rule else 0
        result.append({"rate_bps": rate, "label": rule.label if rule else "", "amount_toman": (amount-reduction)*rate//10000})
    return result


def unit_amount(total, quantity, positions):
    """Stable unit allocation; all positions sum exactly to the original component."""
    return sum(total*(position+1)//quantity-total*position//quantity for position in positions)
