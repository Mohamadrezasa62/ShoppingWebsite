from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from commerce.views import _auth, _body
from sellers.models import Seller
from .api import visible_offers
from .merchandising import cards
from .models import Brand, FollowSubscription, Product


def serialize(row):
    target = row.brand if row.brand_id else row.seller
    return {"id": row.pk, "kind": "brand" if row.brand_id else "seller", "target_id": target.pk, "name": target.name}


@require_http_methods(["GET", "POST"])
@csrf_protect
def following(request):
    if error := _auth(request):
        return error
    if request.method == "POST":
        data = _body(request)
        if not data or set(data) != {"kind", "target_id"} or data["kind"] not in ("brand", "seller") or type(data["target_id"]) is not int or data["target_id"] <= 0:
            return JsonResponse({"error": "invalid_follow"}, status=400)
        eligible = visible_offers()
        if data["kind"] == "brand":
            target = get_object_or_404(Brand.objects.filter(is_active=True, pk__in=eligible.values("variant__product__brand_id")), pk=data["target_id"])
        else:
            target = get_object_or_404(Seller.objects.filter(status="approved", pk__in=eligible.values("seller_id")), pk=data["target_id"])
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not user.is_active:
                return JsonResponse({"error": "account_unavailable"}, status=403)
            lookup = {"user": user, data["kind"]: target}
            row = FollowSubscription.objects.filter(**lookup).first()
            if row is None and FollowSubscription.objects.filter(user=user).count() >= 100:
                return JsonResponse({"error": "follow_limit"}, status=409)
            row, _ = FollowSubscription.objects.get_or_create(**lookup)
        return JsonResponse({"following": serialize(row)})
    rows = FollowSubscription.objects.filter(user=request.user).select_related("brand", "seller").order_by("-pk")[:100]
    return JsonResponse({"following": [serialize(row) for row in rows]})


@require_http_methods(["DELETE"])
@csrf_protect
def unfollow(request, follow_id):
    if error := _auth(request):
        return error
    row = get_object_or_404(FollowSubscription, user=request.user, pk=follow_id)
    row.delete()
    return JsonResponse({"deleted": True})


@require_http_methods(["GET"])
def feed(request):
    if error := _auth(request):
        return error
    follows = FollowSubscription.objects.filter(user=request.user)
    from_sellers = visible_offers().filter(seller_id__in=follows.values("seller_id")).values("variant__product_id")
    products = Product.objects.filter(Q(brand_id__in=follows.values("brand_id")) | Q(pk__in=from_sellers))
    return JsonResponse({"products": cards(products, limit=24), "basis": "followed_brands_and_sellers", "note": "No tracking or marketing messages are enabled by following."})
