import re
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.views import _auth
from .api import _body, _reason, _error, _audit
from .campaigns import set_preference, campaign_action
from .models import MarketingCampaign, NotificationPreference


@require_http_methods(["GET", "PATCH"])
@csrf_protect
def preferences(request):
    if error := _auth(request):
        return error
    row = NotificationPreference.objects.filter(user=request.user).first()
    if request.method == "PATCH":
        data = _body(request)
        if data is None or set(data) != {"marketing_in_app"} or type(data["marketing_in_app"]) is not bool:
            return _error("invalid_preferences")
        try:
            row = set_preference(request.user, data["marketing_in_app"])
        except ValueError:
            return _error("account_unavailable", 403)
    return JsonResponse({"marketing_in_app": row.marketing_in_app if row else False, "updated_at": row.updated_at.isoformat() if row else None, "channels": ["in_app"], "transactional_notifications": "always_enabled"})


def campaign_rows():
    return MarketingCampaign.objects.annotate(reserved=Count("recipients"), delivered=Count("recipients", filter=Q(recipients__status="delivered")), skipped=Count("recipients", filter=Q(recipients__status="skipped")))


def serialize(row):
    return {"id": row.pk, "title": row.title, "body": row.body, "link": row.link, "recipient_limit": row.recipient_limit, "starts_at": row.starts_at.isoformat(), "ends_at": row.ends_at.isoformat(), "status": row.status, "reserved": getattr(row, "reserved", 0), "delivered": getattr(row, "delivered", 0), "skipped": getattr(row, "skipped", 0)}


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required("marketplace_manager", "system_administrator")
def campaigns(request):
    if request.method == "GET":
        return JsonResponse({"campaigns": [serialize(row) for row in campaign_rows().order_by("-pk")[:100]]})
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"title", "body", "link", "recipient_limit", "starts_at", "ends_at", "reason"}:
        return _error("invalid_campaign")
    if any(not isinstance(data[key], str) or "\x00" in data[key] or not 3 <= len(data[key].strip()) <= maximum for key, maximum in [("title", 200), ("body", 2000)]):
        return _error("invalid_campaign")
    if not isinstance(data["link"], str) or not re.fullmatch(r"/(?:products|collections|content)/[\w-]+/?", data["link"]) or len(data["link"]) > 500:
        return _error("invalid_campaign_link")
    if type(data["recipient_limit"]) is not int or not 1 <= data["recipient_limit"] <= 10000:
        return _error("invalid_recipient_limit")
    dates = {key: parse_datetime(data[key]) if isinstance(data[key], str) else None for key in ("starts_at", "ends_at")}
    if any(value is None or timezone.is_naive(value) for value in dates.values()) or dates["ends_at"] <= dates["starts_at"] or dates["ends_at"] <= timezone.now():
        return _error("invalid_campaign_window")
    with transaction.atomic():
        row = MarketingCampaign.objects.create(title=data["title"].strip(), body=data["body"].strip(), link=data["link"], recipient_limit=data["recipient_limit"], created_by=request.user, **dates)
        _audit(request, "campaign_created", "campaign", row.pk, reason, {}, {"status": row.status, "recipient_limit": row.recipient_limit})
    return JsonResponse({"campaign": serialize(row)}, status=201)


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("marketplace_manager", "system_administrator")
def action(request, campaign_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"action", "reason"} or data["action"] not in ("launch", "cancel"):
        return _error("invalid_campaign_action")
    get_object_or_404(MarketingCampaign, pk=campaign_id)
    try:
        with transaction.atomic():
            row = campaign_action(campaign_id, data["action"])
            _audit(request, "campaign_action", "campaign", row.pk, reason, {}, {"status": row.status})
    except ValueError:
        return _error("invalid_campaign_transition", 409)
    return JsonResponse({"campaign": serialize(campaign_rows().get(pk=campaign_id))})
