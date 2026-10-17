"""Email/password access for buyers; staff retain their existing OTP challenge."""
from django.contrib.auth import get_user_model, login
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .services import AuthenticationUnavailable, TooManyRequests
from .throttling import limit_peer
from .views import _body, rate_limited

_DUMMY_PASSWORD = make_password("unavailable-email-account-placeholder")


def credentials(request, operation):
    limit_peer(request, operation)
    data = _body(request)
    if not data or not isinstance(data.get("email"), str) or not isinstance(data.get("password"), str):
        raise ValidationError("invalid_credentials")
    email, password = data["email"].strip().lower(), data["password"]
    if len(email) > 254 or not 1 <= len(password) <= 128:
        raise ValidationError("invalid_credentials")
    validate_email(email)
    return data, email, password


@require_POST
@csrf_protect
def sign_in(request):
    try:
        _data, email, password = credentials(request, "email_login")
    except ValidationError:
        return JsonResponse({"error": "invalid_credentials"}, status=400)
    except TooManyRequests as error:
        return rate_limited(error)
    except AuthenticationUnavailable:
        return JsonResponse({"error": "authentication_unavailable"}, status=503)
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().filter(email__iexact=email).first()
        valid = user.check_password(password) if user else check_password(password, _DUMMY_PASSWORD)
        if not user or not valid or not user.is_active:
            return JsonResponse({"error": "invalid_credentials"}, status=401)
        if user.is_staff or user.is_superuser:
            return JsonResponse({"error": "staff_phone_verification_required"}, status=403)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"status": "authenticated"})


@require_POST
@csrf_protect
def register(request):
    try:
        data, email, password = credentials(request, "email_register")
        if len(password) < 10:
            raise ValidationError("password_too_short")
        name = data.get("name", "")
        if not isinstance(name, str) or len(name.strip()) > 150:
            raise ValidationError("invalid_name")
        user = get_user_model()(email=email, first_name=name.strip())
        validate_password(password, user=user)
    except ValidationError:
        return JsonResponse({"error": "invalid_registration"}, status=400)
    except TooManyRequests as error:
        return rate_limited(error)
    except AuthenticationUnavailable:
        return JsonResponse({"error": "authentication_unavailable"}, status=503)
    try:
        with transaction.atomic():
            if get_user_model().objects.filter(email__iexact=email).exists():
                return JsonResponse({"error": "email_unavailable"}, status=409)
            user.set_password(password)
            user.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    except IntegrityError:
        return JsonResponse({"error": "email_unavailable"}, status=409)
    return JsonResponse({"status": "authenticated"}, status=201)
