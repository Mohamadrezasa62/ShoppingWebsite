from django.db.models import Sum
from commerce.models import OrderLine, ReturnLine
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from accounts.roles import staff_role_required
from commerce.models import Order, OrderDelivery, ReturnCase, DeliveryCancellation
from payments.models import LedgerEntry


@require_GET
@staff_role_required("finance_operator", "marketplace_manager", "system_administrator")
def sales(request):
    paid = Order.objects.filter(status="paid")
    received = LedgerEntry.objects.filter(kind="payment_capture").aggregate(total=Sum("amount_toman"))["total"] or 0
    refunded = -(LedgerEntry.objects.filter(kind="payment_refund").aggregate(total=Sum("amount_toman"))["total"] or 0)
    returned_tax = ReturnLine.objects.filter(case__status="refunded").aggregate(total=Sum("tax_amount_toman"))["total"] or 0
    cancelled_tax = OrderLine.objects.filter(delivery__cancellation__status="refunded").aggregate(total=Sum("tax_toman"))["total"] or 0
    return JsonResponse({"paid_tax_toman": paid.aggregate(total=Sum("tax_total_toman"))["total"] or 0, "refunded_tax_toman": returned_tax + cancelled_tax, "paid_orders": paid.count(), "order_total_toman": paid.aggregate(total=Sum("grand_total_toman"))["total"] or 0,
                         "captured_toman": received, "refunded_toman": refunded, "net_received_toman": received - refunded,
                         "deliveries": {status: OrderDelivery.objects.filter(status=status).count() for status in OrderDelivery.Status.values},
                         "open_cancellations": DeliveryCancellation.objects.filter(status__in=("requested", "approved")).count(),
                         "open_returns": ReturnCase.objects.exclude(status__in=("rejected", "refunded")).count(),
                         "note": "Capture totals include review-required captures; paid orders and cash are distinct metrics. Tax totals use order snapshots and confirmed case refunds, not a tax filing or unallocated cash refunds."})


@require_GET
@staff_role_required("finance_operator", "marketplace_manager", "system_administrator")
def seller_performance(request, seller_id):
    from django.shortcuts import get_object_or_404
    from sellers.models import Seller
    from sellers.reports import seller_performance as report
    get_object_or_404(Seller, pk=seller_id)
    return JsonResponse(report(seller_id))
