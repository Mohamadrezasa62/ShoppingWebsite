"""Transactional internal outbox. No external message transport is enabled."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Notification, OutboxEvent

MAX_ATTEMPTS = 5


def emit(event_key, topic, **payload):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Events must be recorded inside the domain transaction")
    event, created = OutboxEvent.objects.get_or_create(event_key=event_key, defaults={"topic": topic, "payload": payload})
    if not created and (event.topic != topic or event.payload != payload):
        raise ValueError("Conflicting event key")
    return event


def handle(event):
    payload = event.payload
    if event.topic == "seller.stock_low":
        from catalog.models import Offer
        from sellers.models import SellerMembership
        offer = Offer.objects.filter(pk=payload["offer_id"], seller_id=payload["seller_id"], seller__status="approved").first()
        if offer is None or offer.available_quantity - offer.reserved_quantity > 5:
            return
        users = SellerMembership.objects.filter(seller_id=offer.seller_id, role="owner", user__is_active=True).order_by("user_id").values_list("user_id", flat=True)[:100]
        for user_id in users:
            Notification.objects.get_or_create(event_key=f"outbox:{event.event_key}:owner:{user_id}", defaults={"user_id": user_id, "title": "موجودی آزاد کم است", "body": f"موجودی آزاد پیشنهاد شمارهٔ {offer.pk} به پنج عدد یا کمتر رسیده است. موجودی انبارها را بررسی کنید.", "link": "/seller-panel/"})
        return
    if event.topic == "catalog.import":
        from catalog.bulk_import import process_import
        process_import(payload["job_id"], payload["attempt"])
        return
    if event.topic == "campaign.scan":
        from .campaigns import scan_campaign
        scan_campaign(payload["campaign_id"], payload["after_id"])
        return
    if event.topic == "campaign.message":
        from .campaigns import deliver_recipient
        deliver_recipient(payload["recipient_id"])
        return
    if event.topic == "product.alert":
        from catalog.models import Product, ProductAlert
        from django.contrib.auth import get_user_model
        if not ProductAlert.objects.filter(generation=payload["generation"], user_id=payload["user_id"], product_id=payload["product_id"]).exists():
            return
        product = Product.objects.filter(pk=payload["product_id"]).first()
        if product is None or not get_user_model().objects.filter(pk=payload["user_id"], is_active=True).exists():
            return
        Notification.objects.get_or_create(event_key=f"outbox:{event.event_key}", defaults={"user_id": payload["user_id"], "title": "اعلان قیمت محصول" if payload["kind"] == "price_drop" else "محصول موجود شد", "body": f"محصول «{product.title}» با شرایط درخواست‌شدهٔ شما موجود است. قیمت و موجودی را هنگام خرید بررسی کنید.", "link": f"/products/{product.slug}/"})
        return
    topic_titles = {
        "dispute.updated": "وضعیت اختلاف سفارش تغییر کرد",
        "cancellation.requested": "درخواست لغو ارسال ثبت شد",
        "cancellation.updated": "درخواست لغو ارسال بررسی شد",
        "order.created": "سفارش ثبت شد",
        "order.paid": "پرداخت سفارش تأیید شد",
        "order.cancelled": "سفارش لغو شد",
        "order.expired": "مهلت پرداخت سفارش پایان یافت",
        "delivery.packing": "سفارش در حال آماده‌سازی است",
        "delivery.shipped": "سفارش ارسال شد",
        "delivery.delivered": "سفارش تحویل شد",
        "delivery.cancelled": "ارسال سفارش لغو شد",
        "return.requested": "درخواست مرجوعی ثبت شد",
        "return.updated": "وضعیت مرجوعی تغییر کرد",
        "return.refunded": "استرداد آزمایشی ثبت شد",
    }
    if event.topic not in topic_titles:
        raise ValueError("Unknown event topic")
    # Store references only: no addresses, phone numbers or provider credentials.
    order_id = payload["order_id"]
    from commerce.models import Order
    order = Order.objects.get(pk=order_id)
    link = "/disputes/" if event.topic.startswith("dispute.") else "/returns/" if event.topic.startswith("return.") else "/orders/"
    Notification.objects.get_or_create(event_key=f"outbox:{event.event_key}", defaults={"user_id": order.user_id, "title": topic_titles[event.topic], "body": f"به‌روزرسانی سفارش شمارهٔ {order_id}. جزئیات را در صفحهٔ سفارش مشاهده کنید.", "link": link})


def process_event(event_id, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        event = OutboxEvent.objects.select_for_update().get(pk=event_id)
        if event.status != "pending" or event.available_at > now:
            return False
        event.attempts += 1
        try:
            # A savepoint rolls back partial handler work on failure.
            with transaction.atomic():
                handle(event)
        except Exception as error:
            event.last_error = type(error).__name__[:100]
            event.status = "dead" if event.attempts >= MAX_ATTEMPTS else "pending"
            event.available_at = now + timedelta(seconds=min(3600, 30 * 2 ** (event.attempts - 1)))
        else:
            event.status = "done"
            event.processed_at = now
            event.last_error = ""
        event.save(update_fields=["attempts", "status", "available_at", "processed_at", "last_error"])
        return event.status == "done"


def drain(limit=100):
    ids = list(OutboxEvent.objects.filter(status="pending", available_at__lte=timezone.now()).order_by("pk").values_list("pk", flat=True)[:limit])
    return sum(process_event(event_id) for event_id in ids)
