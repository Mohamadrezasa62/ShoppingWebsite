from django.shortcuts import get_object_or_404, render
from django.utils.cache import patch_cache_control
from django.views.decorators.http import require_GET
from .models import Order
from .views import _auth


@require_GET
def invoice(request, order_id):
    if error := _auth(request):
        response = error
    else:
        order = get_object_or_404(Order, pk=order_id, user=request.user)
        deliveries = list(order.deliveries.order_by("pk").prefetch_related("lines"))
        for delivery in deliveries:
            delivery.invoice_lines = sorted(delivery.lines.all(), key=lambda row: row.pk)
            delivery.net_items_toman = 0
            delivery.tax_toman = 0
            for row in delivery.invoice_lines:
                row.net_toman = row.line_total_toman - row.discount_toman
                delivery.net_items_toman += row.net_toman
                delivery.tax_toman += row.tax_toman
            delivery.total_toman = delivery.net_items_toman + delivery.shipping_fee_toman + delivery.tax_toman
        response = render(request, "commerce/invoice.html", {"order": order, "deliveries": deliveries})
        response["Content-Disposition"] = f'attachment; filename="order-{order.pk}.html"'
    patch_cache_control(response, private=True, no_store=True, max_age=0)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; sandbox"
    response["Referrer-Policy"] = "no-referrer"
    return response
