import csv
from io import StringIO

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Sum, Value, BigIntegerField
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods
from accounts.roles import staff_role_required
from commerce.models import Order
from commerce.views import _auth
from operations.api import _body, _reason, _error, _audit
from .models import PaymentAttempt
from .orchestration import PaymentError
from .views import verification_budget
from . import zarinpal


FINANCE_ROLES = ('finance_operator', 'system_administrator')


def cursor(request):
    value = request.GET.get('before')
    if value is None:
        return None
    if not value.isascii() or not value.isdigit() or len(value) > 19 or not 1 <= int(value) <= 9223372036854775807:
        raise ValueError()
    return int(value)


def with_cash(rows):
    return rows.annotate(
        cash_captured=Coalesce(Sum('ledger_entries__amount_toman', filter=Q(ledger_entries__kind='payment_capture')), Value(0), output_field=BigIntegerField()),
        cash_refunded=Coalesce(Sum('ledger_entries__amount_toman', filter=Q(ledger_entries__kind='payment_refund')), Value(0), output_field=BigIntegerField()),
    )


def row_data(row, *, owner=False):
    can_verify = row.provider == 'zarinpal' and row.status == 'redirected' and bool(row.gateway_authority)
    can_resume = owner and can_verify and row.order.status == 'pending_payment' and row.order.expires_at > timezone.now() and zarinpal.enabled()
    return {'id': row.pk, 'order_id': row.order_id, 'provider': row.provider, 'status': row.status,
            'amount_toman': row.amount_toman, 'captured_toman': row.cash_captured,
            'refunded_toman': -row.cash_refunded, 'receipt': row.provider_reference,
            'can_verify': can_verify, 'checkout_url': row.checkout_url if can_resume else '',
            'needs_provider_reconciliation': row.status in ('created', 'initiation_unknown'),
            'created_at': row.created_at.isoformat(), 'updated_at': row.updated_at.isoformat()}


def paginated(request, rows, *, owner=False):
    try:
        before = cursor(request)
    except ValueError:
        return _error('invalid_payment_cursor')
    if before:
        rows = rows.filter(pk__lt=before)
    batch = list(with_cash(rows).select_related('order').order_by('-pk')[:26])
    page = batch[:25]
    return JsonResponse({'payments': [row_data(row, owner=owner) for row in page],
                         'has_next': len(batch) > 25, 'next_before': page[-1].pk if len(batch) > 25 else None})


@require_GET
def order_attempts(request, order_id):
    if error := _auth(request):
        return error
    if set(request.GET) - {'before'} or any(len(request.GET.getlist(key)) != 1 for key in request.GET):
        return _error('invalid_payment_filters')
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return paginated(request, PaymentAttempt.objects.filter(order=order), owner=True)


def queue_rows(request):
    if set(request.GET) - {'before', 'status', 'provider'} or any(len(request.GET.getlist(key)) != 1 for key in request.GET):
        return None, _error('invalid_payment_filters')
    rows = PaymentAttempt.objects.all()
    status = request.GET.get('status')
    if status is None:
        rows = rows.filter(status__in=('created', 'initiation_unknown', 'redirected', 'review_required'))
    elif status not in PaymentAttempt.Status.values:
        return None, _error('invalid_payment_status')
    else:
        rows = rows.filter(status=status)
    provider = request.GET.get('provider')
    if provider is not None:
        if provider not in PaymentAttempt.Provider.values:
            return None, _error('invalid_payment_provider')
        rows = rows.filter(provider=provider)
    return rows, None


@require_GET
@staff_role_required(*FINANCE_ROLES)
def queue(request):
    rows, error = queue_rows(request)
    return error if error is not None else paginated(request, rows)


def csv_cell(value):
    text = str(value)
    # Spreadsheet applications can execute formulas even after whitespace.
    if text.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + text
    return text


@require_http_methods(['POST'])
@csrf_protect
@staff_role_required(*FINANCE_ROLES)
def export_queue(request):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or '\x00' in reason or set(data) != {'reason'}:
        return _error('invalid_payment_review')
    rows, error = queue_rows(request)
    if error is not None:
        return error
    try:
        before = cursor(request)
    except ValueError:
        return _error('invalid_payment_cursor')
    with transaction.atomic():
        actor = get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
        if not actor.is_active or not actor.is_staff or not (actor.is_superuser or actor.groups.filter(name__in=FINANCE_ROLES).exists()):
            return _error('forbidden', 403)
        request.user = actor
        if before:
            rows = rows.filter(pk__lt=before)
        batch = list(with_cash(rows).order_by('-pk')[:26])
        page = batch[:25]
        next_before = page[-1].pk if len(batch) > 25 else None
        output = StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['attempt_id', 'order_id', 'provider', 'status', 'expected_toman',
                         'expected_irr', 'captured_toman', 'refunded_toman', 'gateway_authority',
                         'provider_reference', 'needs_provider_reconciliation', 'created_at', 'updated_at'])
        for row in page:
            writer.writerow([csv_cell(value) for value in (
                row.pk, row.order_id, row.provider, row.status, row.amount_toman,
                row.amount_toman * 10, row.cash_captured, -row.cash_refunded,
                row.gateway_authority, row.provider_reference,
                row.status in ('created', 'initiation_unknown'),
                row.created_at.isoformat(), row.updated_at.isoformat())])
        _audit(request, 'payment_queue_exported', 'payment_queue', 'page', reason, {},
               {'attempt_ids': [row.pk for row in page], 'before': before,
                'next_before': next_before, 'status': request.GET.get('status'),
                'provider': request.GET.get('provider')})
        response = HttpResponse('\ufeff' + output.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="payment-reconciliation-page.csv"'
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Referrer-Policy'] = 'no-referrer'
        response['X-Has-Next'] = 'true' if next_before else 'false'
        if next_before:
            response['X-Next-Before'] = str(next_before)
        return response


@require_http_methods(['POST'])
@csrf_protect
@staff_role_required(*FINANCE_ROLES)
def staff_verify(request, attempt_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or '\x00' in reason or set(data) != {'reason'}:
        return _error('invalid_payment_review')
    try:
        with transaction.atomic():
            actor = get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            if not actor.is_active or not actor.is_staff or not (actor.is_superuser or actor.groups.filter(name__in=FINANCE_ROLES).exists()):
                return _error('forbidden', 403)
            request.user = actor
            order_id = get_object_or_404(PaymentAttempt, pk=attempt_id, provider='zarinpal').order_id
            Order.objects.select_for_update().get(pk=order_id)
            attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
            if attempt.status not in ('redirected', 'captured', 'review_required') or not attempt.gateway_authority:
                return _error('provider_reconciliation_required', 409)
            before = {'status': attempt.status}
            verification_budget(attempt)
            result = zarinpal.verify(attempt.pk)
            _audit(request, 'payment_reverified', 'payment', result.pk, reason, before,
                   {'status': result.status, 'order_id': result.order_id})
            output = with_cash(PaymentAttempt.objects.filter(pk=result.pk)).select_related('order').get()
            return JsonResponse({'payment': row_data(output)})
    except PaymentError as error:
        return _error(error.code, error.status)
