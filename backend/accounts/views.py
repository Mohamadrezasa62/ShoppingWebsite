import json

from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .phones import normalize_code, normalize_iran_mobile
from .roles import STAFF_ROLES
from .services import SmsUnavailable, TooManyRequests, request_code, verify_code


def _body(request):
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _phone(value):
    try:
        return normalize_iran_mobile(value)
    except ValueError:
        return None


@require_GET
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"status": "ok"})


@require_POST
@csrf_protect
def request_phone_code(request):
    body = _body(request)
    phone = _phone(body.get("phone")) if body else None
    if not phone:
        return JsonResponse({"error": "invalid_phone"}, status=400)
    try:
        request_code(phone)
    except TooManyRequests:
        return JsonResponse({"error": "rate_limited"}, status=429)
    except SmsUnavailable:
        return JsonResponse({"error": "sms_unavailable"}, status=503)
    return JsonResponse({"status": "sent"}, status=202)


@require_POST
@csrf_protect
def verify_phone_code(request):
    body = _body(request)
    phone = _phone(body.get("phone")) if body else None
    code = normalize_code(body.get("code", "")) if body else ""
    if not phone or not (code.isascii() and code.isdecimal() and len(code) == 6):
        return JsonResponse({"error": "invalid_request"}, status=400)
    if not verify_code(phone, code):
        return JsonResponse({"error": "invalid_code"}, status=400)
    user, _created = get_user_model().objects.get_or_create(phone=phone, defaults={"password": make_password(None)})
    if not user.is_active:
        return JsonResponse({"error": "account_unavailable"}, status=403)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"status": "authenticated"})


@require_POST
@csrf_protect
def sign_out(request):
    logout(request)
    return JsonResponse({"status": "signed_out"})


@require_GET
def me(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    memberships = list(request.user.seller_memberships.select_related("seller").values(
        "seller_id", "seller__name", "seller__status", "role"
    ))
    return JsonResponse({
        "id": request.user.pk,
        "phone": request.user.phone,
        "is_staff": request.user.is_staff,
        "can_access_admin": request.user.is_staff and (
            request.user.is_superuser or request.user.groups.filter(name__in=STAFF_ROLES).exists()
        ),
        "seller_memberships": memberships,
    })
