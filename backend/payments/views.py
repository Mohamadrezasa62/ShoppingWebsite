from django.http import JsonResponse, HttpResponseRedirect
from django.core.cache import cache
from django.utils.crypto import constant_time_compare
import time
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import get_object_or_404
from commerce.views import _auth, _body
from .orchestration import PaymentError, initiate_sandbox, sandbox_enabled, simulate_result

from .models import PaymentAttempt
from . import zarinpal


@require_GET
def methods(_request):
    available = []
    if zarinpal.enabled():
        available.append({"id": "zarinpal", "label": "پرداخت امن زرین‌پال", "simulated": False})
    if sandbox_enabled():
        available.append({"id": "sandbox", "label": "پرداخت شبیه‌سازی‌شده؛ بدون انتقال پول", "simulated": True})
    return JsonResponse({"available": available,
        "planned": [{"id": value, "enabled": False, "reason": "merchant_onboarding_required"} for value in PaymentAttempt.Provider.values if value not in {item['id'] for item in available} and value != 'sandbox']})



def attempt_data(attempt):
    return {"id": attempt.pk, "order_id": attempt.order_id, "provider": attempt.provider,
            "status": attempt.status, "amount_toman": attempt.amount_toman,
            "checkout_url": attempt.checkout_url, "simulated": attempt.provider == "sandbox"}


@require_http_methods(["POST"])
@csrf_protect
def initiate(request):
    if error := _auth(request):
        return error
    data = _body(request)
    if not data or set(data) != {"order_id", "provider", "idempotency_key"} or type(data["order_id"]) is not int:
        return JsonResponse({"error": "invalid_payment"}, status=400)
    if data["provider"] not in ("sandbox", "zarinpal"):
        return JsonResponse({"error": "provider_unavailable"}, status=503)
    try:
        start = zarinpal.initiate if data["provider"] == "zarinpal" else initiate_sandbox
        attempt = start(request.user, data["order_id"], data["idempotency_key"])
    except PaymentError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    return JsonResponse({"payment": attempt_data(attempt)})


@require_GET
def detail(request, attempt_id):
    if error := _auth(request):
        return error
    attempt = get_object_or_404(PaymentAttempt, pk=attempt_id, order__user=request.user)
    return JsonResponse({"payment": attempt_data(attempt)})


@require_http_methods(["POST"])
@csrf_protect
def sandbox_result(request, attempt_id):
    if error := _auth(request):
        return error
    data = _body(request)
    if not data or set(data) != {"outcome"}:
        return JsonResponse({"error": "invalid_outcome"}, status=400)
    try:
        attempt = simulate_result(request.user, attempt_id, data["outcome"])
    except PaymentError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    return JsonResponse({"payment": attempt_data(attempt)})


def verification_budget(attempt):
    now = int(time.time())
    key = f'payment:verify:{attempt.pk}:{now // 600}'
    try:
        cache.add(key, 0, 1200)
        if cache.incr(key) > 20:
            raise PaymentError('verification_rate_limited', 429)
    except PaymentError:
        raise
    except Exception:
        raise PaymentError('verification_unavailable', 503) from None


@require_GET
def zarinpal_callback(request, token):
    attempt = get_object_or_404(PaymentAttempt, callback_token=token, provider='zarinpal')
    if set(request.GET) != {'Authority', 'Status'} or any(len(request.GET.getlist(key)) != 1 for key in request.GET) or not attempt.gateway_authority or not constant_time_compare(request.GET['Authority'], attempt.gateway_authority):
        return JsonResponse({'error': 'invalid_payment_callback'}, status=400)
    if request.GET['Status'] not in ('OK', 'NOK'):
        return JsonResponse({'error': 'invalid_payment_callback'}, status=400)
    if request.GET['Status'] == 'OK':
        try:
            verification_budget(attempt)
            zarinpal.verify(attempt.pk)
        except PaymentError as error:
            response = JsonResponse({'error': error.code}, status=error.status)
            response['Referrer-Policy'] = 'no-referrer'
            return response
    response = HttpResponseRedirect('/orders/')
    response['Referrer-Policy'] = 'no-referrer'
    response['Cache-Control'] = 'no-store'
    return response


@require_http_methods(['POST'])
@csrf_protect
def verify_live(request, attempt_id):
    if error := _auth(request):
        return error
    attempt = get_object_or_404(PaymentAttempt, pk=attempt_id, order__user=request.user, provider='zarinpal')
    if _body(request) != {}:
        return JsonResponse({'error': 'invalid_verification'}, status=400)
    try:
        verification_budget(attempt)
        result = zarinpal.verify(attempt.pk)
    except PaymentError as error:
        return JsonResponse({'error': error.code}, status=error.status)
    return JsonResponse({'payment': attempt_data(result)})
