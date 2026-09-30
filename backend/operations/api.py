import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from accounts.roles import STAFF_ROLES, staff_role_required
from catalog.models import Category
from sellers.models import Seller

from .models import AuditEvent


def _body(request):
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _error(code, status=400, details=None):
    data = {"error": code}
    if details:
        data["details"] = details
    return JsonResponse(data, status=status)


def _reason(data):
    value = data.get("reason", "")
    return value.strip() if isinstance(value, str) and 3 <= len(value.strip()) <= 500 else None


def _audit(request, action, target_type, target_id, reason, before, after):
    AuditEvent.objects.create(
        actor=request.user,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        reason=reason,
        before=before,
        after=after,
    )


def _category_data(category):
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "parent_id": category.parent_id,
        "is_active": category.is_active,
    }


@require_http_methods(["GET"])
@staff_role_required(*STAFF_ROLES)
def summary(_request):
    return JsonResponse({
        "pending_sellers": Seller.objects.filter(status__in=[Seller.Status.APPLIED, Seller.Status.UNDER_REVIEW]).count(),
        "approved_sellers": Seller.objects.filter(status=Seller.Status.APPROVED).count(),
        "categories": Category.objects.count(),
        "staff_users": get_user_model().objects.filter(is_staff=True).count(),
    })


@require_http_methods(["GET"])
@staff_role_required("marketplace_manager", "system_administrator")
def sellers(_request):
    rows = Seller.objects.order_by("-created_at", "-id")[:100]
    return JsonResponse({"sellers": [
        {
            "id": seller.id,
            "name": seller.name,
            "status": seller.status,
            "created_at": seller.created_at.isoformat(),
            "review_note": seller.review_note,
        }
        for seller in rows
    ]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("marketplace_manager", "system_administrator")
def decide_seller(request, seller_id):
    data = _body(request)
    reason = _reason(data) if data else None
    desired = data.get("status") if data else None
    allowed = {
        Seller.Status.APPLIED: {Seller.Status.UNDER_REVIEW, Seller.Status.APPROVED, Seller.Status.REJECTED},
        Seller.Status.UNDER_REVIEW: {Seller.Status.APPROVED, Seller.Status.REJECTED},
        Seller.Status.APPROVED: {Seller.Status.SUSPENDED},
        Seller.Status.SUSPENDED: {Seller.Status.APPROVED},
        Seller.Status.REJECTED: {Seller.Status.UNDER_REVIEW},
    }
    if not reason or desired not in Seller.Status.values:
        return _error("invalid_decision")
    with transaction.atomic():
        seller = get_object_or_404(Seller.objects.select_for_update(), pk=seller_id)
        if desired not in allowed.get(seller.status, set()):
            return _error("invalid_transition", status=409)
        before = {"status": seller.status, "review_note": seller.review_note}
        seller.status = desired
        seller.review_note = reason
        seller.reviewed_at = timezone.now()
        seller.reviewed_by = request.user
        seller.save(update_fields=["status", "review_note", "reviewed_at", "reviewed_by"])
        after = {"status": seller.status, "review_note": seller.review_note}
        _audit(request, "seller_decision", "seller", seller.pk, reason, before, after)
    return JsonResponse({"seller": {"id": seller.pk, **after}})


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required("catalog_operator", "marketplace_manager", "system_administrator")
def categories(request):
    if request.method == "GET":
        return JsonResponse({"categories": [_category_data(row) for row in Category.objects.select_related("parent")[:500]]})
    data = _body(request)
    reason = _reason(data) if data else None
    name = data.get("name", "").strip() if data and isinstance(data.get("name"), str) else ""
    raw_slug = data.get("slug") if data else None
    slug = slugify(raw_slug or name, allow_unicode=True) if isinstance(raw_slug, (str, type(None))) else ""
    parent_id = data.get("parent_id") if data else None
    if not reason or not name or not slug or not isinstance(parent_id, (int, type(None))) or isinstance(parent_id, bool):
        return _error("invalid_category")
    parent = get_object_or_404(Category, pk=parent_id) if parent_id is not None else None
    category = Category(name=name, slug=slug, parent=parent)
    try:
        category.full_clean()
        with transaction.atomic():
            category.save()
            _audit(request, "category_created", "category", category.pk, reason, {}, _category_data(category))
    except (ValidationError, IntegrityError) as error:
        return _error("invalid_category", details=str(error))
    return JsonResponse({"category": _category_data(category)}, status=201)


@require_http_methods(["PATCH"])
@csrf_protect
@staff_role_required("catalog_operator", "marketplace_manager", "system_administrator")
def update_category(request, category_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason:
        return _error("reason_required")
    with transaction.atomic():
        category = get_object_or_404(Category.objects.select_for_update(), pk=category_id)
        before = _category_data(category)
        if "name" in data:
            if not isinstance(data["name"], str) or not data["name"].strip():
                return _error("invalid_name")
            category.name = data["name"].strip()
        if "slug" in data:
            if not isinstance(data["slug"], str):
                return _error("invalid_slug")
            category.slug = slugify(data["slug"], allow_unicode=True)
        if "is_active" in data:
            if not isinstance(data["is_active"], bool):
                return _error("invalid_active_flag")
            category.is_active = data["is_active"]
        if "parent_id" in data:
            if data["parent_id"] is not None and (not isinstance(data["parent_id"], int) or isinstance(data["parent_id"], bool)):
                return _error("invalid_parent")
            category.parent = get_object_or_404(Category, pk=data["parent_id"]) if data["parent_id"] else None
        try:
            category.full_clean()
            category.save()
        except (ValidationError, IntegrityError) as error:
            return _error("invalid_category", details=str(error))
        after = _category_data(category)
        _audit(request, "category_updated", "category", category.pk, reason, before, after)
    return JsonResponse({"category": after})


@require_http_methods(["GET"])
@staff_role_required("system_administrator")
def staff(request):
    query = request.GET.get("q", "").strip()
    rows = get_user_model().objects.prefetch_related("groups").order_by("phone")
    if query:
        rows = rows.filter(phone__icontains=query)
    else:
        rows = rows.filter(is_staff=True)
    rows = rows[:100]
    return JsonResponse({"staff": [
        {
            "id": user.pk,
            "phone": user.phone,
            "is_superuser": user.is_superuser,
            "is_staff": user.is_staff,
            "roles": sorted(group.name for group in user.groups.all() if group.name in STAFF_ROLES),
        }
        for user in rows
    ]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("system_administrator")
def set_staff_roles(request, user_id):
    data = _body(request)
    reason = _reason(data) if data else None
    roles = data.get("roles") if data else None
    if not reason or not isinstance(roles, list) or not all(isinstance(role, str) and role in STAFF_ROLES for role in roles):
        return _error("invalid_roles")
    roles = sorted(set(roles))
    with transaction.atomic():
        user = get_object_or_404(get_user_model().objects.select_for_update(), pk=user_id)
        if user.pk == request.user.pk or user.is_superuser:
            return _error("protected_account", status=409)
        if roles and not user.has_usable_password():
            return _error("staff_password_setup_required", status=409)
        before = {"is_staff": user.is_staff, "roles": sorted(user.groups.filter(name__in=STAFF_ROLES).values_list("name", flat=True))}
        assigned_groups = Group.objects.filter(name__in=roles)
        if assigned_groups.count() != len(roles):
            return _error("roles_not_seeded", status=409)
        user.groups.remove(*Group.objects.filter(user=user, name__in=STAFF_ROLES))
        user.groups.add(*assigned_groups)
        user.is_staff = bool(roles)
        user.save(update_fields=["is_staff"])
        after = {"is_staff": user.is_staff, "roles": roles}
        _audit(request, "staff_roles_changed", "user", user.pk, reason, before, after)
    return JsonResponse({"staff": {"id": user.pk, "phone": user.phone, **after}})


@require_http_methods(["GET"])
@staff_role_required("system_administrator")
def audit_log(_request):
    rows = AuditEvent.objects.select_related("actor")[:100]
    return JsonResponse({"events": [
        {
            "id": event.pk,
            "created_at": event.created_at.isoformat(),
            "actor": event.actor.phone if event.actor else None,
            "action": event.action,
            "target_type": event.target_type,
            "target_id": event.target_id,
            "reason": event.reason,
            "before": event.before,
            "after": event.after,
        }
        for event in rows
    ]})
