import hashlib
import json
from functools import wraps
from uuid import UUID
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import Q, Case, When, Value, IntegerField, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from commerce.models import Order
from commerce.views import _auth
from .api import _audit, _body, _error, _reason
from .models import Notification, SupportTicket, TicketMessage, SupportWriteReceipt


def support_write(*, staff=False):
    """Serialize per actor before ticket locks; persist only successful writes."""
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method != "POST":
                return view(request, *args, **kwargs)
            if error := _auth(request):
                return error
            data = _body(request)
            if not isinstance(data, dict):
                return _error("invalid_request")
            has_key = "request_key" in data
            key = data.pop("request_key", None)
            if has_key:
                try:
                    if not isinstance(key, str):
                        raise ValueError()
                    key = UUID(key)
                except (ValueError, AttributeError):
                    return _error("invalid_request_key")
            digest = hashlib.sha256(json.dumps({"path": request.path, "data": data}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
            request._body = json.dumps(data).encode()
            with transaction.atomic():
                actor = get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
                if not actor.is_active or (staff and (not actor.is_staff or not (actor.is_superuser or actor.groups.filter(name__in=SUPPORT_ROLES).exists()))):
                    return _error("forbidden", 403)
                request.user = actor
                receipt = SupportWriteReceipt.objects.filter(actor=actor, request_key=key).select_related("ticket").first() if key else None
                if receipt:
                    if receipt.payload_digest != digest:
                        return _error("idempotency_conflict", 409)
                    return JsonResponse({"ticket": ticket_data(receipt.ticket, internal=staff), "replayed": True}, status=receipt.response_status)
                response = view(request, *args, **kwargs)
                if key and 200 <= response.status_code < 300:
                    ticket_id = json.loads(response.content)["ticket"]["id"]
                    SupportWriteReceipt.objects.create(actor=actor, request_key=key, payload_digest=digest, ticket_id=ticket_id, response_status=response.status_code)
                return response
        return wrapped
    return decorate


MESSAGE_PAGE_SIZE = 20
TICKET_PAGE_SIZE = 25


def ticket_data(row, internal=False, before=None):
    messages = getattr(row, "message_window", None) if before is None else None
    if messages is None:
        query = row.messages.all()
        if not internal:
            query = query.filter(is_internal=False)
        if before is not None:
            query = query.filter(pk__lt=before)
        messages = list(query.order_by("-pk")[:MESSAGE_PAGE_SIZE + 1])
    has_older = len(messages) > MESSAGE_PAGE_SIZE
    messages = list(reversed(messages[:MESSAGE_PAGE_SIZE]))
    return {"id": row.pk, "order_id": row.order_id, "subject": row.subject, "status": row.status,
            **({"priority": row.priority, "is_escalated": row.is_escalated} if internal else {}),
            "assigned_to": row.assigned_to_id if internal else None,
            "has_older_messages": has_older,
            "before_message": messages[0].pk if has_older else None,
            "messages": [{"id": item.pk, "body": item.body, "from_support": item.author_id != row.user_id,
                          "is_internal": item.is_internal, "created_at": item.created_at.isoformat()} for item in messages]}


def positive_parameter(request, name, default=None, maximum=9223372036854775807):
    value = request.GET.get(name)
    if value is None:
        return default
    if len(request.GET.getlist(name)) != 1 or not value.isascii() or not value.isdigit() or len(value) > 19:
        raise ValueError()
    result = int(value)
    if not 1 <= result <= maximum:
        raise ValueError()
    return result


def ticket_queue(request, rows, *, internal=False):
    allowed = {"page", "status"} | ({"priority", "assigned", "escalated"} if internal else set())
    if set(request.GET) - allowed or any(len(request.GET.getlist(key)) != 1 for key in request.GET):
        return _error("invalid_ticket_filters")
    try:
        page = positive_parameter(request, "page", 1, 10000)
    except ValueError:
        return _error("invalid_page")
    status = request.GET.get("status")
    if status is not None:
        if status not in ("open", "awaiting_customer", "resolved", "closed"):
            return _error("invalid_status")
        rows = rows.filter(status=status)
    if internal:
        priority = request.GET.get("priority")
        assigned = request.GET.get("assigned")
        escalated = request.GET.get("escalated")
        if priority is not None:
            if priority not in ("normal", "high", "urgent"):
                return _error("invalid_priority")
            rows = rows.filter(priority=priority)
        if assigned is not None:
            if assigned not in ("mine", "unassigned"):
                return _error("invalid_assignment")
            rows = rows.filter(assigned_to_id=request.user.pk if assigned == "mine" else None)
        if escalated is not None:
            if escalated not in ("true", "false"):
                return _error("invalid_escalation")
            rows = rows.filter(is_escalated=escalated == "true")
    messages = TicketMessage.objects.order_by("-pk")
    if not internal:
        messages = messages.filter(is_internal=False)
    start = (page - 1) * TICKET_PAGE_SIZE
    rows = list(rows.prefetch_related(Prefetch("messages", queryset=messages[:MESSAGE_PAGE_SIZE + 1], to_attr="message_window"))[start:start + TICKET_PAGE_SIZE + 1])
    return JsonResponse({"tickets": [ticket_data(row, internal=internal) for row in rows[:TICKET_PAGE_SIZE]],
                         "page": page, "has_next": len(rows) > TICKET_PAGE_SIZE})


def conversation_page(request, ticket_id, *, internal=False):
    if set(request.GET) - {"before"}:
        return _error("invalid_message_cursor")
    try:
        before = positive_parameter(request, "before")
    except ValueError:
        return _error("invalid_message_cursor")
    rows = SupportTicket.objects.all() if internal else SupportTicket.objects.filter(user=request.user)
    row = get_object_or_404(rows, pk=ticket_id)
    return JsonResponse({"ticket": ticket_data(row, internal=internal, before=before)})


@require_http_methods(["GET"])
def conversation(request, ticket_id):
    if error := _auth(request):
        return error
    return conversation_page(request, ticket_id)


@require_http_methods(["GET"])
@staff_role_required("support_agent", "marketplace_manager", "system_administrator")
def staff_conversation(request, ticket_id):
    return conversation_page(request, ticket_id, internal=True)


def message_text(data):
    value = data.get("body") if data else None
    return value.strip() if isinstance(value, str) and "\x00" not in value and 1 <= len(value.strip()) <= 5000 else None


@require_http_methods(["GET", "POST"])
@csrf_protect
@support_write()
def tickets(request):
    if error := _auth(request):
        return error
    if request.method == "POST":
        data = _body(request)
        text = message_text(data)
        subject = data.get("subject", "") if data else ""
        if not text or not isinstance(subject, str) or "\x00" in subject or not 3 <= len(subject.strip()) <= 200 or not set(data).issubset({"subject", "body", "order_id"}):
            return _error("invalid_ticket")
        order_id = data.get("order_id")
        if order_id is not None and (type(order_id) is not int or order_id < 1):
            return _error("invalid_order_id")
        order = get_object_or_404(Order, pk=order_id, user=request.user) if order_id else None
        with transaction.atomic():
            row = SupportTicket.objects.create(user=request.user, order=order, subject=subject.strip())
            TicketMessage.objects.create(ticket=row, author=request.user, body=text)
        return JsonResponse({"ticket": ticket_data(row)}, status=201)
    rows = SupportTicket.objects.filter(user=request.user).order_by("-updated_at", "-pk")
    return ticket_queue(request, rows)


@require_http_methods(["POST"])
@csrf_protect
@support_write()
def reply(request, ticket_id):
    if error := _auth(request):
        return error
    data = _body(request)
    text = message_text(data)
    if not text or set(data) != {"body"}:
        return _error("invalid_message")
    with transaction.atomic():
        row = get_object_or_404(SupportTicket.objects.select_for_update(), pk=ticket_id, user=request.user)
        if row.status == "closed":
            return _error("ticket_closed", 409)
        TicketMessage.objects.create(ticket=row, author=request.user, body=text)
        row.status = "open"
        row.save(update_fields=["status", "updated_at"])
    return JsonResponse({"ticket": ticket_data(row)})


@require_http_methods(["GET"])
@staff_role_required("support_agent", "marketplace_manager", "system_administrator")
def staff_tickets(request):
    rows = SupportTicket.objects.annotate(priority_rank=Case(When(priority="urgent", then=Value(2)), When(priority="high", then=Value(1)), default=Value(0), output_field=IntegerField())).order_by("-is_escalated", "-priority_rank", "-updated_at", "-pk")
    return ticket_queue(request, rows, internal=True)


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("support_agent", "marketplace_manager", "system_administrator")
@support_write(staff=True)
def staff_reply(request, ticket_id):
    data = _body(request)
    text = message_text(data)
    reason = _reason(data) if data else None
    if not reason or not text or set(data) - {"body", "status", "is_internal", "reason"} or data.get("status") not in ("open", "awaiting_customer", "resolved", "closed") or type(data.get("is_internal", False)) is not bool:
        return _error("invalid_ticket_update")
    with transaction.atomic():
        row = get_object_or_404(SupportTicket.objects.select_for_update(), pk=ticket_id)
        if row.is_escalated and data["status"] in ("resolved", "closed"):
            return _error("resolve_escalation_first", 409)
        before = {"status": row.status, "assigned_to": row.assigned_to_id}
        msg = TicketMessage.objects.create(ticket=row, author=request.user, body=text, is_internal=data.get("is_internal", False))
        row.status = data["status"]
        if row.assigned_to_id is None:
            row.assigned_to = request.user
        row.save(update_fields=["status", "assigned_to", "updated_at"])
        _audit(request, "support_reply", "ticket", row.pk, reason, before, {"status": row.status, "assigned_to": row.assigned_to_id})
        if not msg.is_internal:
            Notification.objects.get_or_create(event_key=f"ticket-reply:{msg.pk}", defaults={"user": row.user, "title": "پاسخ پشتیبانی", "body": f"برای درخواست «{row.subject}» پاسخ جدید ثبت شد.", "link": "/support/"})
    return JsonResponse({"ticket": ticket_data(row, internal=True)})


SUPPORT_ROLES = ("support_agent", "marketplace_manager", "system_administrator")
ESCALATION_ROLES = ("marketplace_manager", "system_administrator")


def eligible_assignees():
    return get_user_model().objects.filter(is_active=True, is_staff=True).filter(Q(is_superuser=True) | Q(groups__name__in=SUPPORT_ROLES)).distinct()


@require_http_methods(["GET"])
@staff_role_required(*SUPPORT_ROLES)
def assignees(request):
    rows = eligible_assignees().order_by("pk")[:100]
    return JsonResponse({"assignees": [{"id": row.pk, "name": row.get_full_name() or f"Staff #{row.pk}"} for row in rows]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required(*SUPPORT_ROLES)
@support_write(staff=True)
def route(request, ticket_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"assigned_to", "priority", "is_escalated", "reason"} or (data["assigned_to"] is not None and type(data["assigned_to"]) is not int) or data["priority"] not in ("normal", "high", "urgent") or type(data["is_escalated"]) is not bool:
        return _error("invalid_ticket_route")
    with transaction.atomic():
        row = get_object_or_404(SupportTicket.objects.select_for_update(), pk=ticket_id)
        if row.status == "closed":
            return _error("ticket_closed", 409)
        if data["is_escalated"] and row.status == "resolved":
            return _error("reopen_ticket_first", 409)
        assignee = get_object_or_404(eligible_assignees(), pk=data["assigned_to"]) if data["assigned_to"] is not None else None
        if data["is_escalated"] and (assignee is None or not (assignee.is_superuser or assignee.groups.filter(name__in=ESCALATION_ROLES).exists())):
            return _error("escalation_manager_required")
        if row.is_escalated and not data["is_escalated"] and not (request.user.is_superuser or request.user.groups.filter(name__in=ESCALATION_ROLES).exists()):
            return _error("escalation_review_required", 403)
        before = {"assigned_to": row.assigned_to_id, "priority": row.priority, "is_escalated": row.is_escalated}
        row.assigned_to, row.priority, row.is_escalated = assignee, data["priority"], data["is_escalated"]
        row.save(update_fields=["assigned_to", "priority", "is_escalated", "updated_at"])
        _audit(request, "support_routed", "ticket", row.pk, reason, before, {"assigned_to": row.assigned_to_id, "priority": row.priority, "is_escalated": row.is_escalated})
    return JsonResponse({"ticket": ticket_data(row, internal=True)})


@require_http_methods(["GET"])
def notifications(request):
    if error := _auth(request):
        return error
    rows = Notification.objects.filter(user=request.user).order_by("-pk")[:100]
    return JsonResponse({"notifications": [{"id": row.pk, "title": row.title, "body": row.body, "link": row.link, "read": row.read_at is not None} for row in rows]})


@require_http_methods(["POST"])
@csrf_protect
def read_notification(request, notification_id):
    if error := _auth(request):
        return error
    row = get_object_or_404(Notification, pk=notification_id, user=request.user)
    Notification.objects.filter(pk=row.pk, read_at__isnull=True).update(read_at=timezone.now())
    return JsonResponse({"read": True})
