from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from operations.api import _body, _reason
from .models import AccountClosure
from .closure import ClosureError, blockers, blockers_many, request_closure, withdraw_closure, decide_closure


def serialize(case):
    return {"id": case.pk, "status": case.status, "reason": case.reason, "review_note": case.review_note, "created_at": case.created_at.isoformat()}


def error(exc):
    return JsonResponse({"error": exc.code}, status=exc.status)


@require_http_methods(["GET", "POST"])
@csrf_protect
def requests(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    if request.method == "GET":
        return JsonResponse({"requests": [serialize(row) for row in AccountClosure.objects.filter(user=request.user).order_by("-pk")[:20]], "blockers": blockers(request.user), "retention": "Account access is disabled after review; financial and identity records are retained. This is not data erasure."})
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"reason"}:
        return JsonResponse({"error": "reason_required"}, status=400)
    try:
        case = request_closure(request.user, reason)
    except ClosureError as exc:
        return error(exc)
    return JsonResponse({"request": serialize(case)})


@require_http_methods(["POST"])
@csrf_protect
def withdraw(request, case_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    data = _body(request)
    if data != {}:
        return JsonResponse({"error": "invalid_request"}, status=400)
    try:
        case = withdraw_closure(request.user, case_id)
    except ClosureError as exc:
        return error(exc)
    return JsonResponse({"request": serialize(case)})


@require_http_methods(["GET"])
@staff_role_required("system_administrator")
def staff_requests(request):
    rows = list(AccountClosure.objects.order_by("-pk")[:100])
    holds = blockers_many([row.user_id for row in rows])
    return JsonResponse({"requests": [{**serialize(row), "user_id": row.user_id, "blockers": holds[row.user_id]} for row in rows]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("system_administrator")
def decision(request, case_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"reason", "status"}:
        return JsonResponse({"error": "invalid_closure_decision"}, status=400)
    try:
        case = decide_closure(case_id, data["status"], request.user, reason)
    except ClosureError as exc:
        return error(exc)
    return JsonResponse({"request": serialize(case)})
