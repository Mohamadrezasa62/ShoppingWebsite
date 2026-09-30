from celery import shared_task
from django.utils import timezone

from .models import Order
from .services import expire_order


@shared_task
def expire_due_orders():
    now = timezone.now()
    ids = Order.objects.filter(status=Order.Status.PENDING_PAYMENT, expires_at__lte=now).values_list("pk", flat=True)[:500]
    for order_id in list(ids):
        expire_order(order_id, now)
