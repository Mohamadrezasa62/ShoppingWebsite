from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone

from operations.events import emit
from .models import Order, OrderDelivery, ReturnCase, DeliveryCancellation


class FulfillmentError(Exception):
    pass


ALLOWED_TRANSITIONS = {
    OrderDelivery.Status.AWAITING_FULFILLMENT: {OrderDelivery.Status.PACKING},
    OrderDelivery.Status.PACKING: {OrderDelivery.Status.SHIPPED},
    OrderDelivery.Status.SHIPPED: {OrderDelivery.Status.DELIVERED},
}


def transition_delivery(delivery_id, new_status, tracking_code=""):
    with transaction.atomic():
        order_id = OrderDelivery.objects.values_list("order_id", flat=True).get(pk=delivery_id)
        order = Order.objects.select_for_update().get(pk=order_id)
        delivery = OrderDelivery.objects.select_for_update().get(pk=delivery_id)
        if order.status != Order.Status.PAID:
            raise FulfillmentError("Order must be paid")
        if new_status in (OrderDelivery.Status.PACKING, OrderDelivery.Status.SHIPPED) and order.risk_cases.filter(hold_fulfillment=True).exclude(status="cleared").exists():
            raise FulfillmentError("Operational review holds fulfillment")
        if new_status == "cancelled" or DeliveryCancellation.objects.filter(delivery=delivery, status__in=("requested", "approved")).exists():
            raise FulfillmentError("Cancellation workflow holds delivery")
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
        emit(f"delivery:{delivery.pk}:{new_status}", f"delivery.{new_status}", order_id=order.pk, delivery_id=delivery.pk)
        return delivery


def request_return(delivery_id, buyer, reason, amount_toman):
    with transaction.atomic():
        account = get_user_model().objects.select_for_update().get(pk=buyer.pk)
        if not account.is_active:
            raise FulfillmentError("Account is unavailable")
        order_id = OrderDelivery.objects.values_list("order_id", flat=True).get(pk=delivery_id)
        order = Order.objects.select_for_update().get(pk=order_id)
        delivery = OrderDelivery.objects.select_for_update().get(pk=delivery_id)
        if order.user_id != buyer.pk or delivery.status != OrderDelivery.Status.DELIVERED:
            raise FulfillmentError("Return is not available")
        if delivery.return_cases.exclude(status="rejected").exists():
            raise FulfillmentError("Use quantity-based return service for additional cases")
        maximum = sum(line.line_total_toman for line in delivery.lines.all()) + delivery.shipping_fee_toman
        if not reason.strip() or amount_toman <= 0 or amount_toman > maximum:
            raise FulfillmentError("Invalid return request")
        return ReturnCase.objects.create(
            delivery=delivery, requested_by=buyer, reason=reason.strip(),
            requested_amount_toman=amount_toman,
        )
