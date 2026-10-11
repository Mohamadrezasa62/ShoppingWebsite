from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from catalog.models import ProductQuestion
from .api import _audit, _body, _error, _reason


@require_http_methods(["GET"])
@staff_role_required("catalog_operator", "support_agent", "system_administrator")
def questions(request):
    status = request.GET.get("status", "pending")
    if status not in ("pending", "published", "rejected"):
        return _error("invalid_status")
    rows = ProductQuestion.objects.filter(status=status).select_related("product").order_by("-pk")[:100]
    return JsonResponse({"questions": [{"id": q.pk, "product": q.product.title, "body": q.body, "answer": q.answer, "status": q.status} for q in rows]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("catalog_operator", "support_agent", "system_administrator")
def decision(request, question_id):
    data = _body(request)
    reason = _reason(data) if data else None
    status = data.get("status") if data else None
    answer = data.get("answer", "") if data else None
    if not reason or status not in ("published", "rejected", "pending") or not isinstance(answer, str) or len(answer.strip()) > 4000 or (status == "published" and len(answer.strip()) < 3):
        return _error("invalid_question_decision")
    with transaction.atomic():
        question = get_object_or_404(ProductQuestion.objects.select_for_update(), pk=question_id)
        before = {"status": question.status, "answer": question.answer}
        question.status, question.answer = status, answer.strip()
        question.answered_by = request.user if question.answer else None
        question.save(update_fields=["status", "answer", "answered_by", "updated_at"])
        _audit(request, "question_moderated", "question", question.pk, reason, before, {"status": status, "answer": question.answer})
    return JsonResponse({"status": question.status})
