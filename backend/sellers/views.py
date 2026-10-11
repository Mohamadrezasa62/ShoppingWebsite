import json

from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from catalog.models import Offer, Product, Variant
from catalog.inventory import InventoryError, activate_locked, set_total_locked
from accounts.phones import normalize_iran_mobile

from .models import Seller, SellerMembership

MAX_PRICE_TOMAN = 9_000_000_000_000_000_000
MAX_STOCK = 2_147_483_647


def _data(request):
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _auth(request):
    return None if request.user.is_authenticated else JsonResponse({"error": "authentication_required"}, status=401)


def _membership(request, seller_id):
    return get_object_or_404(SellerMembership.objects.select_related("seller"), user=request.user, seller_id=seller_id)


def _offer_data(offer):
    return {
        "id": offer.pk, "variant_id": offer.variant_id, "product_title": offer.variant.product.title,
        "sku": offer.variant.sku, "price_toman": offer.price_toman,
        "available_quantity": offer.available_quantity, "reserved_quantity": offer.reserved_quantity,
        "warranty": offer.warranty, "fulfillment": offer.fulfillment, "status": offer.status,
        "inventory_managed": offer.inventory_managed,
    }


@require_http_methods(["GET"])
def my_stores(request):
    if error := _auth(request):
        return error
    memberships = SellerMembership.objects.filter(user=request.user).select_related("seller")
    return JsonResponse({"stores": [{
        "id": membership.seller_id, "name": membership.seller.name,
        "role": membership.role, "status": membership.seller.status,
        "description": membership.seller.description, "contact_phone": membership.seller.contact_phone,
    } for membership in memberships]})


@require_http_methods(["POST"])
@csrf_protect
def apply(request):
    if error := _auth(request):
        return error
    data = _data(request)
    name = data.get("name", "").strip() if data and isinstance(data.get("name"), str) else ""
    legal_name = data.get("legal_name", "").strip() if data and isinstance(data.get("legal_name"), str) else ""
    business_identifier = data.get("business_identifier", "").strip() if data and isinstance(data.get("business_identifier"), str) else ""
    try:
        contact_phone = normalize_iran_mobile(data.get("contact_phone", "") if data else "")
    except ValueError:
        return JsonResponse({"error": "invalid_contact_phone"}, status=400)
    if not 3 <= len(name) <= 200 or not 3 <= len(legal_name) <= 200 or not 8 <= len(business_identifier) <= 32:
        return JsonResponse({"error": "invalid_application"}, status=400)
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if not user.is_active:
            return JsonResponse({"error": "account_unavailable"}, status=403)
        seller = Seller.objects.create(name=name, legal_name=legal_name, business_identifier=business_identifier, contact_phone=contact_phone)
        SellerMembership.objects.create(seller=seller, user=request.user, role=SellerMembership.Role.OWNER)
    return JsonResponse({"store": {"id": seller.pk, "name": seller.name, "status": seller.status}}, status=201)


@require_http_methods(["PATCH"])
@csrf_protect
def update_profile(request, seller_id):
    if error := _auth(request):
        return error
    membership = _membership(request, seller_id)
    if membership.role != SellerMembership.Role.OWNER or membership.seller.status != Seller.Status.APPROVED:
        return JsonResponse({"error": "forbidden"}, status=403)
    data = _data(request)
    if not data or not set(data).issubset({"description", "contact_phone"}):
        return JsonResponse({"error": "invalid_profile"}, status=400)
    seller = membership.seller
    if "description" in data:
        if not isinstance(data["description"], str) or len(data["description"]) > 2000:
            return JsonResponse({"error": "invalid_description"}, status=400)
        seller.description = data["description"].strip()
    if "contact_phone" in data:
        try:
            seller.contact_phone = normalize_iran_mobile(data["contact_phone"])
        except ValueError:
            return JsonResponse({"error": "invalid_contact_phone"}, status=400)
    seller.save(update_fields=[key for key in ("description", "contact_phone") if key in data])
    return JsonResponse({"store": {"id": seller.pk, "description": seller.description, "contact_phone": seller.contact_phone}})


@require_http_methods(["GET"])
def catalog_variants(request):
    if error := _auth(request):
        return error
    if not SellerMembership.objects.filter(user=request.user, seller__status=Seller.Status.APPROVED).exists():
        return JsonResponse({"error": "seller_approval_required"}, status=403)
    query = request.GET.get("q", "").strip()[:120]
    if len(query) < 2:
        return JsonResponse({"variants": []})
    rows = Variant.objects.filter(
        is_active=True, product__status=Product.Status.PUBLISHED,
        product__category__is_active=True,
    ).filter(Q(product__brand__isnull=True) | Q(product__brand__is_active=True)).filter(
        Q(product__title__icontains=query) | Q(sku__icontains=query)
    ).select_related("product").order_by("product__title", "sku")[:20]
    return JsonResponse({"variants": [{"id": row.pk, "sku": row.sku, "product_title": row.product.title, "attributes": row.attributes} for row in rows]})


@require_http_methods(["GET", "POST"])
@csrf_protect
def offers(request, seller_id):
    if error := _auth(request):
        return error
    membership = _membership(request, seller_id)
    if membership.seller.status != Seller.Status.APPROVED:
        return JsonResponse({"error": "seller_approval_required"}, status=403)
    if request.method == "GET":
        rows = Offer.objects.filter(seller_id=seller_id).select_related("variant__product").order_by("-updated_at", "-id")[:100]
        return JsonResponse({"offers": [_offer_data(row) for row in rows]})
    data = _data(request)
    if not data:
        return JsonResponse({"error": "invalid_offer"}, status=400)
    variant_id = data.get("variant_id")
    price = data.get("price_toman")
    quantity = data.get("available_quantity")
    warranty = data.get("warranty", "")
    fulfillment = data.get("fulfillment", Offer.Fulfillment.SELLER)
    if not isinstance(variant_id, int) or isinstance(variant_id, bool) or not isinstance(price, int) or isinstance(price, bool) or not 0 < price <= MAX_PRICE_TOMAN or not isinstance(quantity, int) or isinstance(quantity, bool) or not 0 <= quantity <= MAX_STOCK or not isinstance(warranty, str) or len(warranty) > 200 or fulfillment not in Offer.Fulfillment.values:
        return JsonResponse({"error": "invalid_offer"}, status=400)
    variant = get_object_or_404(Variant.objects.select_related("product__category", "product__brand"), pk=variant_id, is_active=True, product__status=Product.Status.PUBLISHED, product__category__is_active=True)
    if variant.product.brand and not variant.product.brand.is_active:
        return JsonResponse({"error": "catalog_unavailable"}, status=409)
    try:
        with transaction.atomic():
            from .inventory_views import authorize_locked
            authorize_locked(request.user, seller_id)
            offer = Offer.objects.create(
                seller=membership.seller, variant=variant, price_toman=price,
                available_quantity=quantity, warranty=warranty.strip(), fulfillment=fulfillment,
                status=Offer.Status.ACTIVE if quantity else Offer.Status.DRAFT,
            )
            activate_locked(offer, request.user)
    except InventoryError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    except IntegrityError:
        return JsonResponse({"error": "offer_already_exists"}, status=409)
    return JsonResponse({"offer": _offer_data(offer)}, status=201)


@require_http_methods(["PATCH"])
@csrf_protect
def update_offer(request, seller_id, offer_id):
    if error := _auth(request):
        return error
    membership = _membership(request, seller_id)
    if membership.seller.status != Seller.Status.APPROVED:
        return JsonResponse({"error": "seller_approval_required"}, status=403)
    data = _data(request)
    if not data or not set(data).issubset({"price_toman", "available_quantity", "warranty", "fulfillment", "status"}):
        return JsonResponse({"error": "invalid_offer"}, status=400)
    with transaction.atomic():
        from .inventory_views import authorize_locked
        try:
            authorize_locked(request.user, seller_id)
        except InventoryError as error:
            return JsonResponse({"error": error.code}, status=error.status)
        offer = get_object_or_404(Offer.objects.select_for_update(of=("self",)).select_related("variant__product__category", "variant__product__brand"), pk=offer_id, seller_id=seller_id)
        previous_quantity = offer.available_quantity
        if "price_toman" in data:
            value = data["price_toman"]
            if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= MAX_PRICE_TOMAN:
                return JsonResponse({"error": "invalid_price"}, status=400)
            offer.price_toman = value
        if "available_quantity" in data:
            value = data["available_quantity"]
            if not isinstance(value, int) or isinstance(value, bool) or not offer.reserved_quantity <= value <= MAX_STOCK:
                return JsonResponse({"error": "stock_below_reserved"}, status=400)
            offer.available_quantity = value
        if "warranty" in data:
            value = data["warranty"]
            if not isinstance(value, str) or len(value) > 200:
                return JsonResponse({"error": "invalid_warranty"}, status=400)
            offer.warranty = value.strip()
        if "fulfillment" in data:
            if data["fulfillment"] not in Offer.Fulfillment.values:
                return JsonResponse({"error": "invalid_fulfillment"}, status=400)
            offer.fulfillment = data["fulfillment"]
        if "status" in data:
            if data["status"] not in [Offer.Status.ACTIVE, Offer.Status.PAUSED]:
                return JsonResponse({"error": "invalid_status"}, status=400)
            if offer.status in [Offer.Status.REJECTED, Offer.Status.PENDING_REVIEW]:
                return JsonResponse({"error": "offer_under_moderation"}, status=409)
            offer.status = data["status"]
        if offer.status == Offer.Status.ACTIVE and offer.available_quantity <= offer.reserved_quantity:
            return JsonResponse({"error": "stock_unavailable"}, status=400)
        if offer.status == Offer.Status.ACTIVE and (
            not offer.variant.is_active or offer.variant.product.status != Product.Status.PUBLISHED
            or not offer.variant.product.category.is_active
            or (offer.variant.product.brand and not offer.variant.product.brand.is_active)
        ):
            return JsonResponse({"error": "catalog_unavailable"}, status=409)
        desired_quantity = offer.available_quantity
        offer.available_quantity = previous_quantity
        try:
            set_total_locked(offer, desired_quantity, request.user, "Seller updated total stock")
        except InventoryError as error:
            return JsonResponse({"error": error.code}, status=error.status)
        offer.save()
    return JsonResponse({"offer": _offer_data(offer)})
