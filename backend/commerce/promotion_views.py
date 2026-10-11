from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .models import Cart, Coupon
from .promotions import coupon_discount
from .views import _auth, _body, _cart_data


@require_http_methods(["POST", "DELETE"])
@csrf_protect
def cart_coupon(request):
    if error := _auth(request):
        return error
    with transaction.atomic():
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        if request.method == "DELETE":
            cart.coupon = None
        else:
            data = _body(request)
            if not data or set(data) != {"code"} or not isinstance(data["code"], str) or not 1 <= len(data["code"].strip()) <= 64:
                return JsonResponse({"error": "invalid_coupon"}, status=400)
            coupon = get_object_or_404(Coupon, code=data["code"].strip().upper())
            try:
                coupon_discount(coupon, _cart_data(cart)["estimated_subtotal_toman"], request.user)
            except ValueError as error:
                return JsonResponse({"error": str(error)}, status=409)
            cart.coupon = coupon
        cart.save(update_fields=["coupon", "updated_at"])
        return JsonResponse({"cart": _cart_data(cart)})
