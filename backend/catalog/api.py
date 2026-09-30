from django.db.models import F, Min, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from sellers.models import Seller

from .models import Category, Offer, Product


def visible_offers():
    return Offer.objects.filter(
        status=Offer.Status.ACTIVE,
        seller__status=Seller.Status.APPROVED,
        variant__is_active=True,
        variant__product__status=Product.Status.PUBLISHED,
        variant__product__category__is_active=True,
        available_quantity__gt=F("reserved_quantity"),
    )


@require_GET
def categories(_request):
    rows = Category.objects.filter(is_active=True).order_by("name", "id")
    return JsonResponse({"categories": [{"id": row.pk, "name": row.name, "slug": row.slug, "parent_id": row.parent_id} for row in rows]})


@require_GET
def products(request):
    query = request.GET.get("q", "").strip()[:120]
    category_slug = request.GET.get("category", "").strip()[:160]
    sort = request.GET.get("sort", "relevance")
    try:
        page = max(1, min(int(request.GET.get("page", "1")), 1000))
    except ValueError:
        page = 1
    queryset = Product.objects.filter(pk__in=visible_offers().values("variant__product_id"))
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(brand__name__icontains=query))
    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)
    queryset = queryset.select_related("brand", "category").annotate(starting_price_toman=Min(
        "variants__offers__price_toman", filter=Q(variants__offers__pk__in=visible_offers().values("pk"))
    ))
    if sort == "price_asc":
        queryset = queryset.order_by("starting_price_toman", "id")
    elif sort == "price_desc":
        queryset = queryset.order_by("-starting_price_toman", "id")
    else:
        queryset = queryset.order_by("-created_at", "-id")
    start = (page - 1) * 24
    rows = queryset[start:start + 25]
    has_next = len(rows) > 24
    return JsonResponse({"products": [{
        "id": row.pk, "title": row.title, "slug": row.slug,
        "category": row.category.name, "brand": row.brand.name if row.brand else None,
        "starting_price_toman": row.starting_price_toman,
    } for row in rows[:24]], "page": page, "has_next": has_next})


@require_GET
def product_detail(_request, slug):
    product = get_object_or_404(
        Product.objects.select_related("brand", "category"),
        slug=slug, status=Product.Status.PUBLISHED, category__is_active=True,
    )
    offers = visible_offers().filter(variant__product=product).select_related("seller", "variant").order_by("price_toman", "id")
    offer_rows = [{
        "id": offer.pk, "seller": {"id": offer.seller_id, "name": offer.seller.name},
        "variant": {"id": offer.variant_id, "sku": offer.variant.sku, "attributes": offer.variant.attributes},
        "price_toman": offer.price_toman, "warranty": offer.warranty,
        "fulfillment": offer.fulfillment, "available_quantity": offer.available_quantity - offer.reserved_quantity,
    } for offer in offers]
    if not offer_rows:
        return JsonResponse({"error": "not_found"}, status=404)
    return JsonResponse({"product": {
        "id": product.pk, "title": product.title, "slug": product.slug,
        "description": product.description, "specifications": product.specifications,
        "category": {"name": product.category.name, "slug": product.category.slug},
        "brand": product.brand.name if product.brand else None, "offers": offer_rows,
    }})
