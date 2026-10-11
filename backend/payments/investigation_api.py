from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from accounts.roles import staff_role_required
from operations.api import _body, _reason, _error, _audit
from .models import PaymentAttempt, PaymentInvestigationNote
from .reconciliation_api import FINANCE_ROLES, cursor


def note_data(note):
    return {'id': note.pk, 'attempt_id': note.attempt_id, 'actor_id': note.actor_id,
            'body': note.body, 'created_at': note.created_at.isoformat()}


@require_GET
@staff_role_required(*FINANCE_ROLES)
def history(request, attempt_id):
    if set(request.GET) - {'before'} or any(len(request.GET.getlist(k)) != 1 for k in request.GET):
        return _error('invalid_payment_filters')
    try:
        before = cursor(request)
    except ValueError:
        return _error('invalid_payment_cursor')
    get_object_or_404(PaymentAttempt, pk=attempt_id)
    rows = PaymentInvestigationNote.objects.filter(attempt_id=attempt_id)
    if before:
        rows = rows.filter(pk__lt=before)
    batch = list(rows.order_by('-pk')[:21])
    page = batch[:20]
    return JsonResponse({'notes': [note_data(note) for note in page],
                         'has_next': len(batch) > 20,
                         'next_before': page[-1].pk if len(batch) > 20 else None})


@require_POST
@csrf_protect
@staff_role_required(*FINANCE_ROLES)
def append(request, attempt_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or '\x00' in reason or set(data) != {'reason', 'request_key'}:
        return _error('invalid_payment_note')
    value = data.get('request_key')
    try:
        if not isinstance(value, str) or len(value) != 36:
            raise ValueError()
        key = UUID(value)
        if str(key) != value or key.int == 0:
            raise ValueError()
    except ValueError:
        return _error('invalid_payment_note_key')
    with transaction.atomic():
        actor = get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
        if not actor.is_active or not actor.is_staff or not (actor.is_superuser or actor.groups.filter(name__in=FINANCE_ROLES).exists()):
            return _error('forbidden', 403)
        request.user = actor
        attempt = get_object_or_404(PaymentAttempt, pk=attempt_id)
        existing = PaymentInvestigationNote.objects.filter(actor=actor, request_key=key).first()
        if existing:
            if existing.attempt_id != attempt.pk or existing.body != reason:
                return _error('payment_note_key_conflict', 409)
            return JsonResponse({'note': note_data(existing), 'replayed': True})
        note = PaymentInvestigationNote.objects.create(attempt=attempt, actor=actor, request_key=key, body=reason)
        _audit(request, 'payment_investigation_noted', 'payment', attempt.pk, reason, {}, {'note_id': note.pk})
        return JsonResponse({'note': note_data(note), 'replayed': False}, status=201)
