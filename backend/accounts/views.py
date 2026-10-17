import json

from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .phones import normalize_code, normalize_iran_mobile
from .roles import STAFF_ROLES
from .throttling import limit_peer, AuthenticationUnavailable
from .services import SmsUnavailable, TooManyRequests, consume_code, request_code, verified_challenge


class AuthenticationRejected(Exception):
    def __init__(self, code, status=400):
        self.code, self.status = code, status


def rate_limited(error):
    response = JsonResponse({"error": "rate_limited"}, status=429)
    response["Retry-After"] = str(error.retry_after)
    return response


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
        limit_peer(request, "request")
        request_code(phone)
    except TooManyRequests as error:
        return rate_limited(error)
    except SmsUnavailable:
        return JsonResponse({"error": "sms_unavailable"}, status=503)
    except AuthenticationUnavailable:
        return JsonResponse({"error": "authentication_unavailable"}, status=503)
    return JsonResponse({"status": "sent"}, status=202)


@require_POST
@csrf_protect
def verify_phone_code(request):
    body = _body(request)
    phone = _phone(body.get("phone")) if body else None
    code = normalize_code(body.get("code", "")) if body else ""
    if not phone or not (code.isascii() and code.isdecimal() and len(code) == 6):
        return JsonResponse({"error": "invalid_request"}, status=400)
    password = body.get("password", "")
    if not isinstance(password, str) or len(password) > 1024:
        return JsonResponse({"error": "invalid_request"}, status=400)
    try:
        limit_peer(request, "verify")
        nonce = verified_challenge(phone, code)
        if nonce is None:
            return JsonResponse({"error": "invalid_code"}, status=400)
        with transaction.atomic():
            user, _created = get_user_model().objects.get_or_create(phone=phone, defaults={"password": make_password(None)})
            user = get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
            if not user.is_active:
                raise AuthenticationRejected("account_unavailable", 403)
            if user.is_staff and not user.check_password(password):
                raise AuthenticationRejected("invalid_staff_credentials")
            if not consume_code(phone, expected_nonce=nonce, code=code):
                raise AuthenticationRejected("invalid_code")
    except AuthenticationRejected as error:
        return JsonResponse({"error": error.code}, status=error.status)
    except TooManyRequests as error:
        return rate_limited(error)
    except AuthenticationUnavailable:
        return JsonResponse({"error": "authentication_unavailable"}, status=503)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"status": "authenticated"})


@require_POST
@csrf_protect
def sign_out(request):
    logout(request)
    return JsonResponse({"status": "signed_out"})


@require_POST
@csrf_protect
def revoke_sessions(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    get_user_model().objects.filter(pk=request.user.pk).update(session_version=F("session_version") + 1)
    logout(request)
    return JsonResponse({"status": "all_sessions_revoked"})


@require_http_methods(["GET", "PATCH"])
@csrf_protect
def me(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    if request.method == "PATCH":
        data = _body(request)
        if not data or not set(data).issubset({"first_name", "last_name"}):
            return JsonResponse({"error": "invalid_profile"}, status=400)
        for key, value in data.items():
            if not isinstance(value, str) or len(value.strip()) > 150:
                return JsonResponse({"error": "invalid_profile"}, status=400)
        for key, value in data.items():
            setattr(request.user, key, value.strip())
        request.user.save(update_fields=list(data))
    memberships = list(request.user.seller_memberships.select_related("seller").values(
        "seller_id", "seller__name", "seller__status", "role"
    ))
    from catalog.models import BrowsingPreference
    return JsonResponse({
        "id": request.user.pk,
        "phone": request.user.phone,
        "email": request.user.email,
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
        "is_staff": request.user.is_staff,
        "can_access_admin": request.user.is_staff and (
            request.user.is_superuser or request.user.groups.filter(name__in=STAFF_ROLES).exists()
        ),
        "staff_roles": sorted(
            request.user.groups.filter(name__in=STAFF_ROLES).values_list("name", flat=True)
        ),
        "is_superuser": request.user.is_superuser,
        "browsing_history_enabled": BrowsingPreference.objects.filter(user=request.user, enabled=True).exists(),
        "seller_memberships": memberships,
    })
