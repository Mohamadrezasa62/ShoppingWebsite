from django.db.models import F, Sum
from commerce.models import OrderDelivery, OrderLine, ReturnLine, DeliveryCancellation
from catalog.models import Offer


def seller_performance(seller_id):
    deliveries = OrderDelivery.objects.filter(seller_id=seller_id, order__status="paid")
    lines = OrderLine.objects.filter(delivery__in=deliveries)
    delivered = lines.filter(delivery__status="delivered")
    returns = ReturnLine.objects.filter(order_line__delivery__seller_id=seller_id, case__status="refunded")
    cancelled_lines = lines.filter(delivery__cancellation__status="refunded")
    cancelled_units = cancelled_lines.aggregate(total=Sum("quantity"))["total"] or 0
    cancelled_item_total = cancelled_lines.aggregate(total=Sum(F("line_total_toman") - F("discount_toman")))["total"] or 0
    cancelled_tax = cancelled_lines.aggregate(total=Sum("tax_toman"))["total"] or 0
    returned_tax = returns.aggregate(total=Sum("tax_amount_toman"))["total"] or 0
    cancelled_total = DeliveryCancellation.objects.filter(delivery__seller_id=seller_id, status="refunded").aggregate(total=Sum("amount_toman"))["total"] or 0
    offers = Offer.objects.filter(seller_id=seller_id)
    return {
        "seller_id": seller_id,
        "period": "all_time",
        "paid_item_tax_toman": lines.aggregate(total=Sum("tax_toman"))["total"] or 0,
        "refunded_tax_toman": returned_tax + cancelled_tax,
        "paid_orders": deliveries.values("order_id").distinct().count(),
        "paid_item_total_toman": lines.aggregate(total=Sum(F("line_total_toman") - F("discount_toman")))["total"] or 0,
        "delivered_units": delivered.aggregate(total=Sum("quantity"))["total"] or 0,
        "refunded_units": (returns.aggregate(total=Sum("quantity"))["total"] or 0) + cancelled_units,
        "cancelled_units": cancelled_units,
        "cancelled_shipping_refund_toman": cancelled_total - cancelled_item_total - cancelled_tax,
        "refunded_item_total_toman": (returns.aggregate(total=Sum("amount_toman"))["total"] or 0) - returned_tax + cancelled_item_total,
        "deliveries": {status: deliveries.filter(status=status).count() for status in OrderDelivery.Status.values},
        "active_offers": offers.filter(status="active").count(),
        "low_stock_offers": offers.filter(status="active", available_quantity__lte=F("reserved_quantity") + 5).count(),
        "note": "Item totals exclude shipping and tax. Refunded units include confirmed refunds only. Conversion and profit are not inferred.",
    }
