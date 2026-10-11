from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from .api import _audit, _body, _error, _reason
from .models import ContentPage, ContentRevision

ROLES = ("catalog_operator", "marketplace_manager", "system_administrator")
FIELDS = ("title", "slug", "body", "kind", "is_published", "publish_after", "publish_until")


def visible_pages(now=None):
    now = now or timezone.now()
    return ContentPage.objects.filter(is_published=True).filter(Q(publish_after__isnull=True) | Q(publish_after__lte=now)).filter(Q(publish_until__isnull=True) | Q(publish_until__gt=now))


def page_data(row, private=False):
    data = {"id": row.pk, "title": row.title, "slug": row.slug, "body": row.body, "kind": row.kind, "is_published": row.is_published}
    if private:
        data.update(version=row.version, publish_after=row.publish_after.isoformat() if row.publish_after else None,
                    publish_until=row.publish_until.isoformat() if row.publish_until else None)
    return data


def snapshot(row):
    return {key: value for key, value in page_data(row, private=True).items() if key != "id"}


def authorize(request):
    user = get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
    if not user.is_active or not user.is_staff or not (user.is_superuser or user.groups.filter(name__in=ROLES).exists()):
        raise PermissionError()


def date_value(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError()
    parsed = parse_datetime(value)
    if parsed is None or timezone.is_naive(parsed):
        raise ValueError()
    return parsed


def apply_fields(row, data):
    for key in FIELDS:
        if key not in data:
            continue
        value = data[key]
        if key.startswith("publish_"):
            value = date_value(value)
        elif key == "is_published":
            if type(value) is not bool:
                raise ValueError()
        else:
            if not isinstance(value, str):
                raise ValueError()
            value = value.strip()
        setattr(row, key, value)
    if len(row.body) > 50000:
        raise ValueError()
    row.full_clean()


def persist(request, row, reason, before):
    row.save()
    ContentRevision.objects.create(page=row, version=row.version, snapshot=snapshot(row), actor=request.user, reason=reason)
    _audit(request, "content_saved", "content", row.pk, reason, before, page_data(row, private=True))


def preserve_baseline(row):
    # Also supports fixtures or pages created before the migration baseline.
    ContentRevision.objects.get_or_create(page=row, version=row.version, defaults={"snapshot": snapshot(row), "reason": "Baseline captured before revisioned edit"})


@require_http_methods(["GET"])
def pages(request):
    return JsonResponse({"pages": [{"title": row.title, "slug": row.slug, "kind": row.kind} for row in visible_pages().order_by("-updated_at", "-pk")[:100]]})


@require_http_methods(["GET"])
def page(request, slug):
    return JsonResponse({"page": page_data(get_object_or_404(visible_pages(), slug=slug))})


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required(*ROLES)
def staff_pages(request):
    if request.method == "GET":
        raw = request.GET.get("page", "1")
        if not raw.isascii() or not raw.isdecimal() or len(raw) > 5 or not 1 <= int(raw) <= 10000:
            return _error("invalid_content_page")
        number = int(raw)
        batch = list(ContentPage.objects.order_by("-updated_at", "-pk")[(number-1)*25:number*25+1])
        return JsonResponse({"pages": [page_data(row, private=True) for row in batch[:25]], "page": number, "has_next": len(batch) > 25})
    return save_page(request)


@require_http_methods(["PATCH"])
@csrf_protect
@staff_role_required(*ROLES)
def update_page(request, page_id):
    return save_page(request, page_id)


def save_page(request, page_id=None):
    data = _body(request)
    reason = _reason(data) if data else None
    allowed = set(FIELDS) | {"reason"} | ({"version"} if page_id else set())
    if not reason or set(data) - allowed or (page_id and (type(data.get("version")) is not int or data["version"] < 1)):
        return _error("invalid_content")
    try:
        with transaction.atomic():
            authorize(request)
            row = get_object_or_404(ContentPage.objects.select_for_update(), pk=page_id) if page_id else ContentPage()
            if page_id and data["version"] != row.version:
                return _error("content_version_conflict", 409)
            before = page_data(row, private=True) if page_id else {}
            if page_id:
                preserve_baseline(row)
                row.version += 1
            apply_fields(row, data)
            persist(request, row, reason, before)
    except PermissionError:
        return _error("forbidden", 403)
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_content")
    return JsonResponse({"page": page_data(row, private=True)}, status=200 if page_id else 201)


@require_http_methods(["GET"])
@staff_role_required(*ROLES)
def revisions(request, page_id):
    get_object_or_404(ContentPage, pk=page_id)
    raw = request.GET.get("before", "")
    if raw and (not raw.isascii() or not raw.isdecimal() or len(raw) > 10 or int(raw) < 1):
        return _error("invalid_revision_cursor")
    rows = ContentRevision.objects.filter(page_id=page_id).order_by("-version")
    if raw:
        rows = rows.filter(version__lt=int(raw))
    batch = list(rows[:26])
    return JsonResponse({"revisions": [{"version": row.version, "snapshot": row.snapshot, "actor_id": row.actor_id, "reason": row.reason, "created_at": row.created_at.isoformat()} for row in batch[:25]], "next_before": batch[24].version if len(batch) > 25 else None})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required(*ROLES)
def restore(request, page_id):
    data = _body(request)
    if not data or set(data) != {"version", "restore_version", "reason"} or not _reason(data) or any(type(data[key]) is not int or data[key] < 1 for key in ("version", "restore_version")):
        return _error("invalid_content_restore")
    try:
        with transaction.atomic():
            authorize(request)
            row = get_object_or_404(ContentPage.objects.select_for_update(), pk=page_id)
            if row.version != data["version"]:
                return _error("content_version_conflict", 409)
            old = get_object_or_404(ContentRevision, page=row, version=data["restore_version"])
            before = page_data(row, private=True)
            preserve_baseline(row)
            # Restore text into an unpublished draft; historical schedules are not replayed.
            apply_fields(row, {**{key: old.snapshot[key] for key in ("title", "slug", "body", "kind")}, "is_published": False, "publish_after": None, "publish_until": None})
            row.version += 1
            persist(request, row, _reason(data), before)
    except PermissionError:
        return _error("forbidden", 403)
    except (ValueError, ValidationError, IntegrityError):
        return _error("invalid_content_restore")
    return JsonResponse({"page": page_data(row, private=True)})
