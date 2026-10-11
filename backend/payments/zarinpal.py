import json
import hashlib
import re
import secrets
from uuid import UUID
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.utils import timezone
from commerce.models import Order
from .models import PaymentAttempt
from .orchestration import PaymentError
from .services import VerifiedCapture, record_verified_capture


class GatewayUnavailable(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def configuration_valid():
    try:
        merchant = UUID(settings.ZARINPAL_MERCHANT_ID)
        origin = urlsplit(settings.SITE_URL)
        return bool(merchant.int and str(merchant) == settings.ZARINPAL_MERCHANT_ID and origin.scheme == 'https' and origin.hostname and not origin.username and not origin.password and not origin.query and not origin.fragment and origin.path in ('', '/'))
    except (ValueError, AttributeError):
        return False


def enabled():
    return settings.ZARINPAL_ENABLED and configuration_valid()


def post(action, payload):
    request = Request(f'https://payment.zarinpal.com/pg/v4/payment/{action}.json', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, method='POST')
    try:
        with build_opener(NoRedirect()).open(request, timeout=10) as response:
            raw = response.read(65537)
            if response.status != 200 or len(raw) > 65536:
                raise ValueError()
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError()
            data = result.get('data')
            if isinstance(data, dict) and type(data.get('code')) is int:
                return data
            errors = result.get('errors')
            if isinstance(errors, dict) and type(errors.get('code')) is int and errors['code'] < 0:
                return {'code': errors['code']}
            raise ValueError()
    except Exception:
        raise GatewayUnavailable() from None


def initiate(user, order_id, request_key):
    if not enabled():
        raise PaymentError('provider_unavailable', 503)
    try:
        key = UUID(str(request_key))
    except (ValueError, TypeError, AttributeError):
        raise PaymentError('invalid_idempotency_key', 400)
    merchant = settings.ZARINPAL_MERCHANT_ID
    merchant_digest = hashlib.sha256(merchant.encode()).hexdigest()
    with transaction.atomic():
        actor = get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
        if not actor.is_active:
            raise PaymentError("forbidden", 403)
        order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
        if order is None:
            raise PaymentError('order_not_found', 404)
        existing = PaymentAttempt.objects.filter(order=order, idempotency_key=key).first()
        if existing:
            if existing.provider != 'zarinpal':
                raise PaymentError('idempotency_conflict')
            if existing.status in ('created', 'initiation_unknown'):
                raise PaymentError('payment_initiation_unresolved', 503)
            return existing
        if order.status != Order.Status.PENDING_PAYMENT or order.expires_at <= timezone.now() or order.grand_total_toman <= 0:
            raise PaymentError('order_not_payable')
        if PaymentAttempt.objects.filter(order=order).exclude(status='rejected').exists():
            raise PaymentError('active_payment_exists')
        if PaymentAttempt.objects.filter(order=order).count() >= 5:
            raise PaymentError('payment_attempt_limit')
        attempt = PaymentAttempt.objects.create(order=order, provider='zarinpal', amount_toman=order.grand_total_toman, idempotency_key=key, gateway_merchant=merchant_digest, callback_token=secrets.token_hex(32))
    # Persist before contacting the provider. Crash/timeout never automatically retries creation.
    callback = f'{settings.SITE_URL.rstrip("/")}/api/v1/payments/zarinpal/callback/{attempt.callback_token}/'
    try:
        data = post('request', {'merchant_id': merchant, 'amount': attempt.amount_toman * 10, 'currency': 'IRR', 'callback_url': callback, 'description': f'Order {order.pk}'})
        authority = data.get('authority')
        if data['code'] == 100 and isinstance(authority, str) and re.fullmatch(r'[A-Za-z0-9]{20,160}', authority):
            with transaction.atomic():
                locked = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
                locked.gateway_authority = authority
                locked.checkout_url = f'https://payment.zarinpal.com/pg/StartPay/{authority}'
                locked.status = 'redirected'
                locked.save(update_fields=['gateway_authority', 'checkout_url', 'status', 'updated_at'])
                return locked
        if data['code'] < 0:
            PaymentAttempt.objects.filter(pk=attempt.pk).update(status='rejected', updated_at=timezone.now())
            raise PaymentError('gateway_request_rejected', 502)
        raise GatewayUnavailable()
    except GatewayUnavailable:
        PaymentAttempt.objects.filter(pk=attempt.pk).update(status='initiation_unknown', updated_at=timezone.now())
        raise PaymentError('payment_initiation_unresolved', 503) from None


def verify(attempt_id):
    order_id = PaymentAttempt.objects.values_list('order_id', flat=True).get(pk=attempt_id)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id, provider='zarinpal')
        if attempt.status in ('captured', 'review_required'):
            return attempt
        if not attempt.gateway_authority or attempt.status != 'redirected':
            raise PaymentError('payment_not_verifiable')
        # Persist a credential fingerprint, never the merchant secret in payment rows.
        merchant = settings.ZARINPAL_MERCHANT_ID
        if hashlib.sha256(merchant.encode()).hexdigest() != attempt.gateway_merchant:
            raise PaymentError('verification_credentials_changed', 503)
        # Disabling new initiations does not prevent verification with retained credentials.
        try:
            data = post('verify', {'merchant_id': merchant, 'amount': attempt.amount_toman * 10, 'authority': attempt.gateway_authority})
        except GatewayUnavailable:
            raise PaymentError('verification_unavailable', 503) from None
        ref = data.get('ref_id')
        if data['code'] not in (100, 101):
            raise PaymentError('payment_not_verified', 409)
        if type(ref) is not int or ref <= 0 or len(str(ref)) > 80:
            raise PaymentError('verification_unavailable', 503)
        try:
            record_verified_capture(attempt.pk, VerifiedCapture(f'zarinpal:{ref}', attempt.amount_toman, 'TOMAN'))
        except (IntegrityError, ValueError):
            raise PaymentError('verification_conflict', 409) from None
        attempt.refresh_from_db()
        return attempt
