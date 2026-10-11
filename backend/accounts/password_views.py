from django.contrib.auth import get_user_model, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from operations.models import AuditEvent
from .phones import normalize_code
from .services import request_code, verified_challenge, consume_code, SmsUnavailable, TooManyRequests, AuthenticationUnavailable
from .throttling import limit_peer
from .views import _body, AuthenticationRejected, rate_limited

PURPOSE = "staff_password"


def staff(request):
    if not request.user.is_authenticated:
        raise AuthenticationRejected("authentication_required", 401)
    if not request.user.is_active or not request.user.is_staff:
        raise AuthenticationRejected("forbidden", 403)


def failure(error):
    if isinstance(error, AuthenticationRejected):
        return JsonResponse({"error": error.code}, status=error.status)
    if isinstance(error, TooManyRequests):
        return rate_limited(error)
    if isinstance(error, SmsUnavailable):
        return JsonResponse({"error": "sms_unavailable"}, status=503)
    return JsonResponse({"error": "authentication_unavailable"}, status=503)


@require_POST
@csrf_protect
def request_change_code(request):
    try:
        staff(request)
        limit_peer(request, "request")
        request_code(request.user.phone, purpose=PURPOSE)
    except (AuthenticationRejected, TooManyRequests, SmsUnavailable, AuthenticationUnavailable) as error:
        return failure(error)
    return JsonResponse({"status": "sent"}, status=202)


@require_POST
@csrf_protect
def change_password(request):
    try:
        staff(request)
        data = _body(request)
        if not data or set(data) != {"current_password", "new_password", "code"}:
            raise AuthenticationRejected("invalid_password_change")
        if any(not isinstance(data[key], str) or not 1 <= len(data[key]) <= 1024 for key in ("current_password", "new_password")):
            raise AuthenticationRejected("invalid_password_change")
        code = normalize_code(data["code"])
        if not (code.isascii() and code.isdecimal() and len(code) == 6):
            raise AuthenticationRejected("invalid_password_change")
        limit_peer(request, "verify")
        nonce = verified_challenge(request.user.phone, code, purpose=PURPOSE)
        if nonce is None:
            raise AuthenticationRejected("invalid_credentials")
        with transaction.atomic():
            user = get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            if not user.is_active or not user.is_staff:
                raise AuthenticationRejected("forbidden", 403)
            if not user.check_password(data["current_password"]):
                raise AuthenticationRejected("invalid_credentials")
            if data["current_password"] == data["new_password"]:
                raise AuthenticationRejected("password_unchanged")
            try:
                validate_password(data["new_password"], user)
            except ValidationError:
                raise AuthenticationRejected("weak_password")
            if not consume_code(user.phone, expected_nonce=nonce, code=code, purpose=PURPOSE):
                raise AuthenticationRejected("invalid_credentials")
            user.set_password(data["new_password"])
            user.session_version += 1
            user.save(update_fields=["password", "session_version"])
            # Never store hashes, OTPs or password input in audit snapshots.
            AuditEvent.objects.create(actor=user, action="staff_password_changed", target_type="user", target_id=str(user.pk), reason="Self-service staff credential rotation", before={}, after={"sessions_revoked": True})
    except (AuthenticationRejected, TooManyRequests, AuthenticationUnavailable) as error:
        return failure(error)
    logout(request)
    return JsonResponse({"status": "password_changed_sign_in_required"})
