import json
import re

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from catalog.models import Offer
from accounts.phones import normalize_code, normalize_iran_mobile

from .models import Address, Cart, CartLine, Order, OrderDelivery, ShippingRule
from .helpers import address_data, offer_is_visible


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
        available = offer_is_visible(offer) and free_stock >= line.quantity
        line_total = offer.price_toman * line.quantity
        subtotal += line_total
        can_checkout = can_checkout and available
        result.append({
            "id": line.pk, "offer_id": offer.pk, "quantity": line.quantity,
            "product_title": offer.variant.product.title, "product_slug": offer.variant.product.slug,
            "variant": offer.variant.attributes, "seller": offer.seller.name,
            "seller_id": offer.seller_id, "fulfillment": offer.fulfillment,
            "unit_price_toman": offer.price_toman, "line_total_toman": line_total,
            "free_stock": free_stock, "available": available,
        })
    return {"lines": result, "estimated_subtotal_toman": subtotal, "can_checkout": bool(result) and can_checkout,
            "coupon_code": cart.coupon.code if cart.coupon_id else "",
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
    if not offer_is_visible(offer):
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
        line = get_object_or_404(CartLine.objects.select_for_update(of=("self",)).select_related(
            "offer__seller", "offer__variant__product__category", "offer__variant__product__brand"
        ), pk=line_id, cart=user_cart)
        if request.method == "DELETE":
            line.delete()
        else:
            data = _body(request)
            if not data or set(data) != {"quantity"} or not _valid_quantity(data["quantity"]):
                return JsonResponse({"error": "invalid_quantity"}, status=400)
            if not offer_is_visible(line.offer) or data["quantity"] > line.offer.available_quantity - line.offer.reserved_quantity:
                return JsonResponse({"error": "insufficient_stock"}, status=409)
            line.quantity = data["quantity"]
            line.save(update_fields=["quantity"])
    return JsonResponse({"cart": _cart_data(user_cart)})


def _address_fields(data):
    if not data or set(data) != {"full_name", "phone", "province", "city", "street", "postal_code"}:
        return None
    fields = {}
    for key, maximum in (("full_name", 160), ("province", 120), ("city", 120), ("street", 500)):
        value = data[key]
        if not isinstance(value, str) or not 2 <= len(value.strip()) <= maximum:
            return None
        fields[key] = value.strip()
    try:
        fields["phone"] = normalize_iran_mobile(data["phone"])
    except ValueError:
        return None
    postal_code = normalize_code(data["postal_code"])
    if not re.fullmatch(r"\d{10}", postal_code):
        return None
    fields["postal_code"] = postal_code
    return fields


@require_http_methods(["GET", "POST"])
@csrf_protect
def addresses(request):
    if error := _auth(request):
        return error
    if request.method == "GET":
        return JsonResponse({"addresses": [address_data(row) for row in Address.objects.filter(user=request.user).order_by("-created_at", "-id")]})
    fields = _address_fields(_body(request))
    if not fields:
        return JsonResponse({"error": "invalid_address"}, status=400)
    address = Address.objects.create(user=request.user, **fields)
    return JsonResponse({"address": address_data(address)}, status=201)


@require_http_methods(["PATCH", "DELETE"])
@csrf_protect
def delete_address(request, address_id):
    if error := _auth(request):
        return error
    address = get_object_or_404(Address, pk=address_id, user=request.user)
    if request.method == "PATCH":
        data = _body(request)
        allowed = {"full_name", "phone", "province", "city", "street", "postal_code"}
        if not data or not set(data).issubset(allowed):
            return JsonResponse({"error": "invalid_address"}, status=400)
        fields = _address_fields({**{key: getattr(address, key) for key in allowed}, **data})
        if not fields:
            return JsonResponse({"error": "invalid_address"}, status=400)
        for key, value in fields.items():
            setattr(address, key, value)
        address.save(update_fields=list(fields))
        return JsonResponse({"address": address_data(address)})
    address.delete()
    return JsonResponse({"deleted": True})


@require_http_methods(["GET"])
def quote(request):
    if error := _auth(request):
        return error
    raw_id = request.GET.get("address_id", "")
    if not raw_id.isascii() or not raw_id.isdecimal() or len(raw_id) > 18:
        return JsonResponse({"error": "invalid_address_id"}, status=400)
    address = get_object_or_404(Address, pk=int(raw_id), user=request.user)
    user_cart, _ = Cart.objects.get_or_create(user=request.user)
    rows = list(CartLine.objects.filter(cart=user_cart).select_related("offer__seller", "offer__variant__product").order_by("pk"))
    if not rows:
        return JsonResponse({"error": "empty_cart"}, status=409)
    subtotal = sum(row.offer.price_toman * row.quantity for row in rows)
    groups = {(row.offer.seller_id, row.offer.fulfillment): row.offer.seller.name for row in rows}
    rules = {row.fulfillment: row for row in ShippingRule.objects.filter(province=address.province, is_active=True)}
    from .shipping import resolve_choices, resolve_slots, group_key, ShippingChoiceError
    raw_choices = request.GET.get("shipping_methods", "{}")
    try:
        if len(raw_choices) > 4096:
            raise ValueError()
        choices = json.loads(raw_choices)
        selected, options = resolve_choices(groups, rules, choices)
        raw_slots = request.GET.get("shipping_slots", "{}")
        if len(raw_slots) > 4096:
            raise ValueError()
        windows, available_windows = resolve_slots(selected, json.loads(raw_slots))
    except (ValueError, RecursionError):
        return JsonResponse({"error": "invalid_shipping_methods"}, status=400)
    except ShippingChoiceError as error:
        return JsonResponse({"error": error.code}, status=409)
    deliveries = []
    missing = []
    shipping_total = 0
    for (seller_id, fulfillment), seller_name in groups.items():
        rule = rules.get(fulfillment)
        if not rule:
            missing.append({"seller_id": seller_id, "fulfillment": fulfillment})
            continue
        key = group_key(seller_id, fulfillment)
        method = selected[key]
        shipping_total += method["fee_toman"]
        deliveries.append({
            "seller_id": seller_id, "seller": seller_name, "fulfillment": fulfillment,
            "group_key": key, **method, "options": options[key], "window": windows[key], "windows": available_windows[key],
        })
    ready = bool(rows) and all(offer_is_visible(row.offer) and row.quantity <= row.offer.available_quantity - row.offer.reserved_quantity for row in rows) and not missing
    from .promotions import coupon_discount
    try:
        discount = coupon_discount(user_cart.coupon, subtotal, request.user)
        coupon_error = None
    except ValueError as error:
        discount, coupon_error, ready = 0, str(error), False
    from .taxes import calculate_taxes
    taxes = calculate_taxes(rows, {row.offer_id: row.offer for row in rows}, discount)
    tax_total = sum(row["amount_toman"] for row in taxes)
    from .quotes import issue_quote, quote_digest, QUOTE_MAX_AGE
    from .services import MAX_TOTAL_TOMAN
    if subtotal + shipping_total + tax_total > MAX_TOTAL_TOMAN:
        ready = False
    token = issue_quote(request.user.pk, address.pk, quote_digest(address_data(address), rows, {row.offer_id: row.offer for row in rows}, rules, user_cart.coupon, discount, selected, windows, taxes)) if ready else None
    response = JsonResponse({"quote": {
        "address": address_data(address), "item_subtotal_toman": subtotal,
        "shipping_total_toman": shipping_total if ready else None,
        "estimated_total_toman": subtotal + shipping_total - discount + tax_total if ready else None,
        "tax_total_toman": tax_total, "discount_total_toman": discount, "coupon_error": coupon_error,
        "currency": "toman", "deliveries": deliveries, "missing_shipping_rules": missing,
        "ready": ready, "is_final": False,
        "approval_token": token, "valid_for_seconds": QUOTE_MAX_AGE,
        "lines": [{"id": row.pk, "product_title": row.offer.variant.product.title,
                   "seller": row.offer.seller.name, "quantity": row.quantity,
                   "unit_price_toman": row.offer.price_toman,
                   "line_total_toman": row.offer.price_toman * row.quantity,
                   "warranty": row.offer.warranty, "tax": tax} for row, tax in zip(rows, taxes)],
    }})
    response["Cache-Control"] = "private, no-store"
    return response


def _order_data(order):
    deliveries = OrderDelivery.objects.filter(order=order).select_related("cancellation", "dispute").prefetch_related("lines").order_by("id")
    return {
        "id": order.pk, "status": order.status,
        "item_total_toman": order.item_total_toman, "tax_total_toman": order.tax_total_toman,
        "shipping_total_toman": order.shipping_total_toman,
        "grand_total_toman": order.grand_total_toman,
        "discount_total_toman": order.discount_total_toman, "coupon_code": order.coupon_code,
        "currency": "toman", "address": order.address_snapshot,
        "expires_at": order.expires_at.isoformat(),
        "created_at": order.created_at.isoformat(),
        "deliveries": [{
            "id": delivery.pk, "status": delivery.status,
            "dispute_status": delivery.dispute.status if hasattr(delivery, "dispute") else None, "cancellation_status": delivery.cancellation.status if hasattr(delivery, "cancellation") else None,
            "tracking_code": delivery.tracking_code,
            "shipped_at": delivery.shipped_at.isoformat() if delivery.shipped_at else None,
            "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
            "seller": delivery.seller_name, "fulfillment": delivery.fulfillment,
            "shipping_fee_toman": delivery.shipping_fee_toman,
            "shipping_method_code": delivery.shipping_method_code, "shipping_method_label": delivery.shipping_method_label,
            "delivery_window_start": delivery.delivery_window_start.isoformat() if delivery.delivery_window_start else None,
            "delivery_window_end": delivery.delivery_window_end.isoformat() if delivery.delivery_window_end else None,
            "min_days": delivery.min_days, "max_days": delivery.max_days,
            "lines": [{
                "id": line.pk,
                "product_title": line.product_title, "variant": line.variant_attributes,
                "quantity": line.quantity, "unit_price_toman": line.unit_price_toman,
                "line_total_toman": line.line_total_toman, "warranty": line.warranty,
                "discount_toman": line.discount_toman, "tax_toman": line.tax_toman, "tax_rate_bps": line.tax_rate_bps, "tax_label": line.tax_label,
            } for line in delivery.lines.all()],
        } for delivery in deliveries],
    }


def delivery_data(delivery):
    return {"id": delivery.pk, "order_id": delivery.order_id,
            "status": delivery.status, "tracking_code": delivery.tracking_code,
            "shipping_method_label": delivery.shipping_method_label,
            "delivery_window_start": delivery.delivery_window_start.isoformat() if delivery.delivery_window_start else None,
            "delivery_window_end": delivery.delivery_window_end.isoformat() if delivery.delivery_window_end else None,
            "dispute_status": delivery.dispute.status if hasattr(delivery, "dispute") else None, "cancellation_status": delivery.cancellation.status if hasattr(delivery, "cancellation") else None,
            "seller": delivery.seller_name, "shipping_fee_toman": delivery.shipping_fee_toman,
            "lines": [{"id": line.pk, "product_title": line.product_title,
                       "quantity": line.quantity, "unit_price_toman": line.unit_price_toman,
                       "line_total_toman": line.line_total_toman} for line in delivery.lines.all()]}


@require_http_methods(["POST"])
@csrf_protect
def checkout(request):
    if error := _auth(request):
        return error
    data = _body(request)
    if not data or not {"address_id", "idempotency_key"}.issubset(data) or not set(data).issubset({"address_id", "idempotency_key", "quote_token", "shipping_methods", "shipping_slots"}) or not isinstance(data["address_id"], int) or isinstance(data["address_id"], bool) or ("quote_token" in data and not isinstance(data["quote_token"], str)):
        return JsonResponse({"error": "invalid_checkout"}, status=400)
    from .services import CheckoutError, create_order
    try:
        order, created = create_order(request.user, data["address_id"], data["idempotency_key"], data.get("quote_token"), data.get("shipping_methods"), data.get("shipping_slots"))
    except CheckoutError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    return JsonResponse({"order": _order_data(order)}, status=201 if created else 200)


@require_http_methods(["GET"])
def orders(request):
    if error := _auth(request):
        return error
    rows = Order.objects.filter(user=request.user).order_by("-created_at", "-id")[:50]
    return JsonResponse({"orders": [{
        "id": order.pk, "status": order.status, "grand_total_toman": order.grand_total_toman,
        "created_at": order.created_at.isoformat(), "expires_at": order.expires_at.isoformat(),
    } for order in rows]})


@require_http_methods(["GET"])
def order_detail(request, order_id):
    if error := _auth(request):
        return error
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return JsonResponse({"order": _order_data(order)})


@require_http_methods(["POST"])
@csrf_protect
def cancel_order(request, order_id):
    if error := _auth(request):
        return error
    from .services import CheckoutError, cancel_unpaid_order
    try:
        order = cancel_unpaid_order(order_id, request.user)
    except CheckoutError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    return JsonResponse({"order": _order_data(order)})
