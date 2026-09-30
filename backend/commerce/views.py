import json

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from catalog.models import Offer, Product
from sellers.models import Seller

from .models import Cart, CartLine


def _body(request):
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _auth(request):
    return None if request.user.is_authenticated else JsonResponse({"error": "authentication_required"}, status=401)


def _valid_quantity(value):
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 100


def _is_visible(offer):
    product = offer.variant.product
    return (
        offer.status == Offer.Status.ACTIVE
        and offer.seller.status == Seller.Status.APPROVED
        and offer.variant.is_active
        and product.status == Product.Status.PUBLISHED
        and product.category.is_active
        and (product.brand is None or product.brand.is_active)
    )


def _cart_data(cart):
    rows = CartLine.objects.filter(cart=cart).select_related(
        "offer__seller", "offer__variant__product__category", "offer__variant__product__brand"
    ).order_by("id")
    result = []
    subtotal = 0
    can_checkout = True
    for line in rows:
        offer = line.offer
        free_stock = max(0, offer.available_quantity - offer.reserved_quantity)
        available = _is_visible(offer) and free_stock >= line.quantity
        line_total = offer.price_toman * line.quantity
        subtotal += line_total
        can_checkout = can_checkout and available
        result.append({
            "id": line.pk, "offer_id": offer.pk, "quantity": line.quantity,
            "product_title": offer.variant.product.title, "product_slug": offer.variant.product.slug,
            "variant": offer.variant.attributes, "seller": offer.seller.name,
            "unit_price_toman": offer.price_toman, "line_total_toman": line_total,
            "free_stock": free_stock, "available": available,
        })
    return {"lines": result, "estimated_subtotal_toman": subtotal, "can_checkout": bool(result) and can_checkout,
            "shipping_and_fees_calculated": False}


@require_http_methods(["GET", "POST"])
@csrf_protect
def cart(request):
    if error := _auth(request):
        return error
    user_cart, _ = Cart.objects.get_or_create(user=request.user)
    if request.method == "GET":
        return JsonResponse({"cart": _cart_data(user_cart)})
    data = _body(request)
    if not data or not set(data).issubset({"offer_id", "quantity"}) or not _valid_quantity(data.get("quantity")) or not isinstance(data.get("offer_id"), int) or isinstance(data["offer_id"], bool):
        return JsonResponse({"error": "invalid_cart_line"}, status=400)
    offer = get_object_or_404(Offer.objects.select_related(
        "seller", "variant__product__category", "variant__product__brand"
    ), pk=data["offer_id"])
    if not _is_visible(offer):
        return JsonResponse({"error": "offer_unavailable"}, status=409)
    with transaction.atomic():
        Cart.objects.select_for_update().get(pk=user_cart.pk)
        line, created = CartLine.objects.select_for_update().get_or_create(cart=user_cart, offer=offer, defaults={"quantity": data["quantity"]})
        new_quantity = line.quantity if created else line.quantity + data["quantity"]
        if new_quantity > 100 or new_quantity > offer.available_quantity - offer.reserved_quantity:
            if created:
                line.delete()
            return JsonResponse({"error": "insufficient_stock"}, status=409)
        line.quantity = new_quantity
        line.save(update_fields=["quantity"])
    return JsonResponse({"cart": _cart_data(user_cart)}, status=201)


@require_http_methods(["PATCH", "DELETE"])
@csrf_protect
def cart_line(request, line_id):
    if error := _auth(request):
        return error
    user_cart = get_object_or_404(Cart, user=request.user)
    with transaction.atomic():
        line = get_object_or_404(CartLine.objects.select_for_update().select_related(
            "offer__seller", "offer__variant__product__category", "offer__variant__product__brand"
        ), pk=line_id, cart=user_cart)
        if request.method == "DELETE":
            line.delete()
        else:
            data = _body(request)
            if not data or set(data) != {"quantity"} or not _valid_quantity(data["quantity"]):
                return JsonResponse({"error": "invalid_quantity"}, status=400)
            if not _is_visible(line.offer) or data["quantity"] > line.offer.available_quantity - line.offer.reserved_quantity:
                return JsonResponse({"error": "insufficient_stock"}, status=409)
            line.quantity = data["quantity"]
            line.save(update_fields=["quantity"])
    return JsonResponse({"cart": _cart_data(user_cart)})
