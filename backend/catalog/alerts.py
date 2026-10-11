from django.db import transaction
from django.db.models import F, Q, Min
from django.utils import timezone
from operations.events import emit
from .models import Offer, ProductAlert


def scan_alerts(limit=100, after_id=0):
    """Bounded, repeatable scan. Caller advances a keyset cursor between batches."""
    ids = list(ProductAlert.objects.filter(is_active=True, pk__gt=after_id).order_by("pk").values_list("pk", flat=True)[:limit])
    fired = 0
    for alert_id in ids:
        with transaction.atomic():
            row = ProductAlert.objects.select_for_update().filter(pk=alert_id, is_active=True).first()
            if row is None:
                continue
            prices = Offer.objects.filter(variant__product_id=row.product_id, variant__is_active=True, variant__product__status="published", variant__product__category__is_active=True, seller__status="approved", status="active", available_quantity__gt=F("reserved_quantity")).filter(Q(variant__product__brand__isnull=True) | Q(variant__product__brand__is_active=True))
            minimum = prices.aggregate(value=Min("price_toman"))["value"]
            if minimum is None or (row.kind == "price_drop" and minimum > row.target_price_toman):
                continue
            emit(f"product-alert:{row.generation}", "product.alert", user_id=row.user_id, product_id=row.product_id, kind=row.kind, generation=str(row.generation))
            row.is_active, row.notified_at = False, timezone.now()
            row.save(update_fields=["is_active", "notified_at"])
            fired += 1
    return {"fired": fired, "last_id": ids[-1] if ids else after_id, "scanned": len(ids)}
