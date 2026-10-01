from django.db import transaction
from django.utils import timezone

from .models import Order, OrderDelivery, ReturnCase


class FulfillmentError(Exception):
    pass


ALLOWED_TRANSITIONS = {
    OrderDelivery.Status.AWAITING_FULFILLMENT: {OrderDelivery.Status.PACKING, OrderDelivery.Status.CANCELLED},
    OrderDelivery.Status.PACKING: {OrderDelivery.Status.SHIPPED, OrderDelivery.Status.CANCELLED},
    OrderDelivery.Status.SHIPPED: {OrderDelivery.Status.DELIVERED},
}


def transition_delivery(delivery_id, new_status, tracking_code=""):
    with transaction.atomic():
        delivery = OrderDelivery.objects.select_related("order").select_for_update().get(pk=delivery_id)
        if delivery.order.status != Order.Status.PAID:
            raise FulfillmentError("Order must be paid")
        if new_status not in ALLOWED_TRANSITIONS.get(delivery.status, set()):
            raise FulfillmentError("Invalid delivery transition")
        if new_status == OrderDelivery.Status.SHIPPED:
            if not tracking_code.strip():
                raise FulfillmentError("Tracking code is required")
            delivery.tracking_code = tracking_code.strip()
            delivery.shipped_at = timezone.now()
        if new_status == OrderDelivery.Status.DELIVERED:
            delivery.delivered_at = timezone.now()
        delivery.status = new_status
        delivery.save(update_fields=["status", "tracking_code", "shipped_at", "delivered_at"])
        return delivery


def request_return(delivery_id, buyer, reason, amount_toman):
    with transaction.atomic():
        delivery = OrderDelivery.objects.select_related("order").select_for_update().get(pk=delivery_id)
        if delivery.order.user_id != buyer.pk or delivery.status != OrderDelivery.Status.DELIVERED:
            raise FulfillmentError("Return is not available")
        maximum = sum(line.line_total_toman for line in delivery.lines.all()) + delivery.shipping_fee_toman
        if not reason.strip() or amount_toman <= 0 or amount_toman > maximum:
            raise FulfillmentError("Invalid return request")
        return ReturnCase.objects.create(
            delivery=delivery, requested_by=buyer, reason=reason.strip(),
            requested_amount_toman=amount_toman,
        )
