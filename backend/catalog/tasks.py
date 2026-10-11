from celery import shared_task
from django.core.cache import cache
from .alerts import scan_alerts


@shared_task
def check_product_alerts():
    # Persist cursor to avoid starving subscriptions beyond the first batch.
    result = scan_alerts(after_id=cache.get("product-alert-cursor", 0))
    cache.set("product-alert-cursor", result["last_id"] if result["scanned"] == 100 else 0, None)
    return result


@shared_task
def purge_expired_history():
    from .history_api import cutoff
    from .models import RecentProductView
    threshold = cutoff()
    ids = list(RecentProductView.objects.filter(viewed_at__lt=threshold).order_by("viewed_at", "pk").values_list("pk", flat=True)[:1000])
    # Recheck after selecting a bounded batch: a concurrent view can refresh a row.
    return RecentProductView.objects.filter(pk__in=ids, viewed_at__lt=threshold).delete()[0]
