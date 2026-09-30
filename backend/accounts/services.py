import secrets
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
    pass


class SmsUnavailable(Exception):
    pass


def _code_digest(phone, code):
    return salted_hmac("shopping.phone_otp", f"{phone}:{code}", algorithm="sha256").hexdigest()


def deliver_code(phone, code):
    if settings.SMS_BACKEND == "console" and settings.DEBUG:
        print(f"Development OTP for {phone}: {code}", flush=True)
        return
    raise SmsUnavailable("No production SMS provider has been configured")


def request_code(phone):
    if settings.SMS_BACKEND == "disabled":
        raise SmsUnavailable("No SMS provider has been configured")
    cooldown_key = f"otp:cooldown:{phone}"
    if not cache.add(cooldown_key, 1, OTP_COOLDOWN_SECONDS):
        raise TooManyRequests("Wait before requesting another code")

    quota_key = f"otp:quota:{phone}"
    cache.add(quota_key, 0, PHONE_WINDOW_SECONDS)
    if cache.incr(quota_key) > PHONE_MAX_REQUESTS:
        raise TooManyRequests("Too many code requests")

    code = f"{secrets.randbelow(1_000_000):06d}"
    nonce = secrets.token_hex(8)
    record = {"digest": _code_digest(phone, code), "nonce": nonce}
    cache.set(f"otp:code:{phone}", record, OTP_TTL_SECONDS)
    try:
        deliver_code(phone, code)
    except Exception:
        cache.delete(f"otp:code:{phone}")
        cache.delete(cooldown_key)
        raise


def verify_code(phone, code):
    record = cache.get(f"otp:code:{phone}")
    if not record:
        return False
    attempts_key = f"otp:attempts:{phone}:{record['nonce']}"
    cache.add(attempts_key, 0, OTP_TTL_SECONDS)
    if cache.incr(attempts_key) > OTP_MAX_ATTEMPTS:
        return False
    if not compare_digest(record["digest"], _code_digest(phone, code)):
        return False
    cache.delete(f"otp:code:{phone}")
    cache.delete(attempts_key)
    cache.delete(f"otp:cooldown:{phone}")
    return True
