"""Owner-only, opt-in shopping history with bounded retention and no analytics."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from commerce.views import _auth, _body
from .merchandising import cards
from .models import BrowsingPreference, Product, RecentProductView
from .question_api import public_product

MAX_HISTORY = 50
RETENTION_DAYS = 30


def cutoff():
    return timezone.now() - timedelta(days=RETENTION_DAYS)


@require_http_methods(["GET", "PATCH", "DELETE"])
@csrf_protect
def history(request):
    if error := _auth(request):
        return error
    if request.method != "GET":
        data = _body(request) if request.method == "PATCH" else None
        if request.method == "PATCH" and (not data or set(data) != {"enabled"} or type(data["enabled"]) is not bool):
            return JsonResponse({"error": "invalid_browsing_preference"}, status=400)
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not user.is_active:
                return JsonResponse({"error": "account_unavailable"}, status=403)
            if request.method == "PATCH":
                BrowsingPreference.objects.update_or_create(user=user, defaults={"enabled": data["enabled"]})
            if request.method == "DELETE" or not data["enabled"]:
                RecentProductView.objects.filter(user=user).delete()
    enabled = BrowsingPreference.objects.filter(user=request.user, enabled=True).exists()
    views = list(RecentProductView.objects.filter(user=request.user, viewed_at__gte=cutoff()).order_by("-viewed_at", "-pk")[:MAX_HISTORY]) if enabled else []
    products = {row["id"]: row for row in cards(Product.objects.filter(pk__in=[view.product_id for view in views]), limit=MAX_HISTORY)}
    response = JsonResponse({"enabled": enabled, "retention_days": RETENTION_DAYS, "limit": MAX_HISTORY, "products": [{**products[view.product_id], "viewed_at": view.viewed_at.isoformat()} for view in views if view.product_id in products]})
    response["Cache-Control"] = "private, no-store"
    return response


@require_http_methods(["POST"])
@csrf_protect
def record(request):
    if error := _auth(request):
        return error
    data = _body(request)
    if not data or set(data) != {"product_id"} or type(data["product_id"]) is not int or not 1 <= data["product_id"] <= 9_000_000_000_000_000_000:
        return JsonResponse({"error": "invalid_product_id"}, status=400)
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if not user.is_active:
            return JsonResponse({"error": "account_unavailable"}, status=403)
        if not BrowsingPreference.objects.filter(user=user, enabled=True).exists():
            return JsonResponse({"recorded": False})
        product = public_product(data["product_id"])
        RecentProductView.objects.filter(user=user, viewed_at__lt=cutoff()).delete()
        RecentProductView.objects.update_or_create(user=user, product=product, defaults={"viewed_at": timezone.now()})
        keep = list(RecentProductView.objects.filter(user=user).order_by("-viewed_at", "-pk").values_list("pk", flat=True)[:MAX_HISTORY])
        RecentProductView.objects.filter(user=user).exclude(pk__in=keep).delete()
    return JsonResponse({"recorded": True})
