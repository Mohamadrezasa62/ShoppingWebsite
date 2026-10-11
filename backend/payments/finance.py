from django.db import transaction
from django.db.models import Sum
from commerce.models import Order, OrderDelivery
from .models import LedgerEntry


def accrue_delivery(delivery_id):
    """Recognize delivered goods and seller-fulfilled shipping, once per delivery.

    This is a seller payable subledger, not a claim of a certified general ledger.
    Commission is integer-floor per line, with the remainder belonging to seller.
    """
    with transaction.atomic():
        order_id = OrderDelivery.objects.values_list("order_id", flat=True).get(pk=delivery_id)
        order = Order.objects.select_for_update().get(pk=order_id)
        delivery = OrderDelivery.objects.get(pk=delivery_id)
        if order.status != Order.Status.PAID or delivery.status != OrderDelivery.Status.DELIVERED:
            return
        if LedgerEntry.objects.filter(event_key=f"payable-delivery:{delivery.pk}").exists():
            return
        gross = sum(line.line_total_toman - line.discount_toman for line in delivery.lines.all())
        commission = sum((line.line_total_toman - line.discount_toman) * line.commission_bps // 10000 for line in delivery.lines.all())
        shipping = delivery.shipping_fee_toman if delivery.fulfillment == "seller" else 0
        net = gross - commission + shipping
        if net:
            LedgerEntry.objects.create(order=order, seller=delivery.seller, kind="seller_payable", amount_toman=net, event_key=f"payable-delivery:{delivery.pk}")
        if commission:
            LedgerEntry.objects.get_or_create(event_key=f"commission-delivery:{delivery.pk}", defaults={"order": order, "seller": delivery.seller, "kind": "commission", "amount_toman": commission})


def reverse_return_payable(case):
    accrue_delivery(case.delivery_id)
    commission = 0
    for row in case.lines.select_related("order_line"):
        line = row.order_line
        original_commission = (line.line_total_toman - line.discount_toman) * line.commission_bps // 10000
        commission += sum(original_commission * (position + 1) // line.quantity - original_commission * position // line.quantity for position in row.unit_positions)
    tax = sum(row.tax_amount_toman for row in case.lines.all())
    net = case.requested_amount_toman - tax - commission
    if net:
        LedgerEntry.objects.get_or_create(event_key=f"payable-return:{case.pk}", defaults={"order_id": case.delivery.order_id, "seller_id": case.delivery.seller_id, "kind": "seller_payable", "amount_toman": -net})
    if commission:
        LedgerEntry.objects.get_or_create(event_key=f"commission-return:{case.pk}", defaults={"order_id": case.delivery.order_id, "seller_id": case.delivery.seller_id, "kind": "commission", "amount_toman": -commission})
