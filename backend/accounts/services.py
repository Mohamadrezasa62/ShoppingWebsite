import secrets
import time
from hmac import compare_digest

from django.conf import settings
from django.core.cache import cache
from django.utils.crypto import salted_hmac


OTP_TTL_SECONDS = 300
OTP_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
PHONE_WINDOW_SECONDS = 3600
PHONE_MAX_REQUESTS = 5


class TooManyRequests(Exception):
    def __init__(self, message="Rate limited", retry_after=60):
        super().__init__(message)
        self.retry_after = max(1, int(retry_after))


class AuthenticationUnavailable(Exception):
    pass


def cache_call(method, *args, **kwargs):
    try:
        return getattr(cache, method)(*args, **kwargs)
    except Exception as error:
        raise AuthenticationUnavailable() from error


class SmsUnavailable(Exception):
    pass


def _scope(phone, purpose):
    if purpose not in ("login", "staff_password"):
        raise ValueError("Invalid OTP purpose")
    return phone if purpose == "login" else f"{purpose}:{phone}"


def _code_digest(phone, code, purpose="login"):
    return salted_hmac("shopping.phone_otp", f"{_scope(phone, purpose)}:{code}", algorithm="sha256").hexdigest()


def deliver_code(phone, code, *, purpose="login"):
    if settings.SMS_BACKEND == "console" and settings.DEBUG:
        print(f"Development {purpose} OTP for {phone}: {code}", flush=True)
        return
    if settings.SMS_BACKEND == "kavenegar":
        from .sms import send_otp, DeliveryFailure
        try:
            send_otp(phone, code, purpose)
        except DeliveryFailure:
            raise SmsUnavailable("SMS submission unavailable") from None
        return
    raise SmsUnavailable("No production SMS provider has been configured")


def request_code(phone, *, purpose="login"):
    scope = _scope(phone, purpose)
    if settings.SMS_BACKEND == "disabled":
        raise SmsUnavailable("No SMS provider has been configured")
    cooldown_key = f"otp:cooldown:{phone}"
    if not cache_call("add", cooldown_key, 1, OTP_COOLDOWN_SECONDS):
        raise TooManyRequests("Wait before requesting another code")

    now = int(time.time())
    quota_key = f"otp:quota:{phone}:{now//PHONE_WINDOW_SECONDS}"
    cache_call("add", quota_key, 0, PHONE_WINDOW_SECONDS*2)
    if cache_call("incr", quota_key) > PHONE_MAX_REQUESTS:
        raise TooManyRequests("Too many code requests", PHONE_WINDOW_SECONDS-now%PHONE_WINDOW_SECONDS)

    code = f"{secrets.randbelow(1_000_000):06d}"
    nonce = secrets.token_hex(8)
    record = {"digest": _code_digest(phone, code, purpose), "nonce": nonce}
    cache_call("set", f"otp:code:{scope}", record, OTP_TTL_SECONDS)
    try:
        deliver_code(phone, code, purpose=purpose)
    except Exception:
        # Invalidate this failed delivery's nonce without deleting a newer code
        # that may have replaced it while the provider call was in flight.
        cache_call("add", f"otp:consumed:{scope}:{nonce}", 1, OTP_TTL_SECONDS)
        raise


def verified_challenge(phone, code, *, purpose="login"):
    scope = _scope(phone, purpose)
    record = cache_call("get", f"otp:code:{scope}")
    if not record or cache_call("get", f"otp:consumed:{scope}:{record['nonce']}"):
        return None
    attempts_key = f"otp:attempts:{scope}:{record['nonce']}"
    cache_call("add", attempts_key, 0, OTP_TTL_SECONDS*2)
    if cache_call("incr", attempts_key) > OTP_MAX_ATTEMPTS:
        return None
    if not compare_digest(record["digest"], _code_digest(phone, code, purpose)):
        return None
    return record["nonce"]


def verify_code(phone, code, *, consume=True, purpose="login"):
    nonce = verified_challenge(phone, code, purpose=purpose)
    if nonce is None:
        return False
    return consume_code(phone, expected_nonce=nonce, code=code, purpose=purpose) if consume else True


def consume_code(phone, expected_nonce=None, code=None, *, purpose="login"):
    scope = _scope(phone, purpose)
    record = cache_call("get", f"otp:code:{scope}")
    if not record or (expected_nonce is not None and record["nonce"] != expected_nonce):
        return False
    if code is not None and not compare_digest(record["digest"], _code_digest(phone, code, purpose)):
        return False
    # Atomic add consumes one nonce once. Keep the expiring code record instead
    # of deleting it: a delayed old consumer must not delete a replacement code.
    return cache_call("add", f"otp:consumed:{scope}:{record['nonce']}", 1, OTP_TTL_SECONDS)
