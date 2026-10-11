from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.db import transaction
from django.contrib.auth import get_user_model
from commerce.views import _auth, _body
from .models import Product, ProductQuestion


def public_product(product_id):
    return get_object_or_404(Product.objects.filter(Q(brand__isnull=True) | Q(brand__is_active=True)), pk=product_id, status="published", category__is_active=True)


@require_http_methods(["GET", "POST"])
@csrf_protect
def questions(request, product_id):
    product = public_product(product_id)
    if request.method == "POST":
        if error := _auth(request):
            return error
        data = _body(request)
        body = data.get("body") if data else None
        if not data or set(data) != {"body"} or not isinstance(body, str) or not 10 <= len(body.strip()) <= 2000:
            return JsonResponse({"error": "invalid_question"}, status=400)
        # Bound pending submissions without imposing a purchase requirement on questions.
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if ProductQuestion.objects.filter(user=request.user, product=product, status="pending").count() >= 3:
                return JsonResponse({"error": "pending_question_limit"}, status=429)
            question = ProductQuestion.objects.create(user=request.user, product=product, body=body.strip())
        return JsonResponse({"question": {"id": question.pk, "status": question.status}}, status=201)
    rows = ProductQuestion.objects.filter(product=product, status="published").exclude(answer="").order_by("-pk")[:50]
    return JsonResponse({"questions": [{"id": row.pk, "body": row.body, "answer": row.answer} for row in rows]})
