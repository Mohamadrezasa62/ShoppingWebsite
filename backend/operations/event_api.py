from django.db import transaction
from django.db.models import Count, Min
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from .models import OutboxEvent
from .api import _audit, _body, _error, _reason


@require_http_methods(["GET"])
@staff_role_required("system_administrator")
def events(request):
    rows = OutboxEvent.objects.exclude(status="done").order_by("pk")[:100]
    counts = list(OutboxEvent.objects.values("status").annotate(count=Count("id"), oldest=Min("created_at")))
    return JsonResponse({"summary": counts, "events": [{"id": e.pk, "topic": e.topic, "status": e.status, "attempts": e.attempts, "last_error": e.last_error, "available_at": e.available_at.isoformat()} for e in rows]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("system_administrator")
def replay(request, event_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"reason"}:
        return _error("reason_required")
    with transaction.atomic():
        event = get_object_or_404(OutboxEvent.objects.select_for_update(), pk=event_id)
        if event.status != "dead":
            return _error("event_not_dead", 409)
        before = {"status": event.status, "attempts": event.attempts}
        event.status, event.attempts, event.available_at = "pending", 0, timezone.now()
        event.save(update_fields=["status", "attempts", "available_at"])
        _audit(request, "outbox_replayed", "outbox", event.pk, reason, before, {"status": "pending"})
    return JsonResponse({"status": "pending"})
