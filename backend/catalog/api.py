from django.db.models import F, Min, Prefetch, Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from sellers.models import Seller

from .models import Brand, Category, CategoryFacet, Offer, Product, ProductMedia


@require_GET
def sitemap(request):
    from operations.content_api import visible_pages
    rows = Product.objects.filter(status="published", category__is_active=True).filter(Q(brand__isnull=True) | Q(brand__is_active=True)).order_by("pk")[:10000]
    pages = visible_pages().order_by("pk")[:10000]
    from .merchandising import active_collections
    collections = active_collections().order_by("pk")[:10000]
    return JsonResponse({"collections": [{"slug": row.slug, "updated_at": row.updated_at.isoformat()} for row in collections], "products": [{"slug": row.slug, "updated_at": row.updated_at.isoformat()} for row in rows],
                         "pages": [{"slug": row.slug, "updated_at": row.updated_at.isoformat()} for row in pages]})


def visible_offers():
    return Offer.objects.filter(
        status=Offer.Status.ACTIVE,
        seller__status=Seller.Status.APPROVED,
        variant__is_active=True,
        variant__product__status=Product.Status.PUBLISHED,
        variant__product__category__is_active=True,
        available_quantity__gt=F("reserved_quantity"),
    ).filter(Q(variant__product__brand__isnull=True) | Q(variant__product__brand__is_active=True))


def visible_products():
    return Product.objects.filter(status="published", category__is_active=True).filter(Q(brand__isnull=True) | Q(brand__is_active=True))


@require_GET
def categories(_request):
    rows = Category.objects.filter(is_active=True).order_by("name", "id")
    return JsonResponse({"categories": [{"id": row.pk, "name": row.name, "slug": row.slug, "parent_id": row.parent_id} for row in rows]})


@require_GET
def brands(_request):
    rows = Brand.objects.filter(is_active=True, products__pk__in=visible_offers().values("variant__product_id")).distinct().order_by("name")
    return JsonResponse({"brands": [{"name": row.name, "slug": row.slug} for row in rows]})


@require_GET
def facets(request):
    category_slug = request.GET.get("category", "").strip()[:160]
    if not category_slug:
        return JsonResponse({"facets": []})
    category = get_object_or_404(Category, slug=category_slug, is_active=True)
    rows = CategoryFacet.objects.filter(category=category, is_active=True)
    return JsonResponse({"facets": [{"key": row.key, "label": row.label, "choices": row.choices} for row in rows]})


@require_GET
def suggestions(request):
    query = request.GET.get("q", "").strip()[:120]
    if len(query) < 2:
        return JsonResponse({"suggestions": []})
    rows = Product.objects.filter(
        pk__in=visible_offers().values("variant__product_id"), title__icontains=query,
    ).order_by("title", "id")[:8]
    return JsonResponse({"suggestions": [{"title": row.title, "slug": row.slug} for row in rows]})


def _image_data(media):
    return {"url": f"/api/v1/catalog/media/{media.pk}/", "alt": media.alt_text} if media else None


@require_GET
def product_media(_request, media_id):
    media = get_object_or_404(
        ProductMedia.objects.filter(is_approved=True, product_id__in=visible_offers().values("variant__product_id")),
        pk=media_id,
    )
    return FileResponse(media.image.open("rb"))


@require_GET
def products(request):
    query = request.GET.get("q", "").strip()[:120]
    category_slug = request.GET.get("category", "").strip()[:160]
    brand_slug = request.GET.get("brand", "").strip()[:160]
    sort = request.GET.get("sort", "relevance")
    try:
        min_price = int(request.GET.get("min_price", "0") or "0")
        max_price = int(request.GET.get("max_price", "0") or "0")
    except ValueError:
        return JsonResponse({"error": "invalid_price_filter"}, status=400)
    if min_price < 0 or max_price < 0 or (max_price and min_price > max_price):
        return JsonResponse({"error": "invalid_price_filter"}, status=400)
    try:
        page = max(1, min(int(request.GET.get("page", "1")), 1000))
    except ValueError:
        page = 1
    eligible_offers = visible_offers()
    if any(key.startswith("facet_") for key in request.GET) and not category_slug:
        return JsonResponse({"error": "category_required_for_facets"}, status=400)
    if category_slug:
        configured_facets = {row.key: row for row in CategoryFacet.objects.filter(category__slug=category_slug, category__is_active=True, is_active=True)}
        for key, value in request.GET.items():
            if not key.startswith("facet_"):
                continue
            facet = configured_facets.get(key[6:])
            if facet is None or facet.key in CategoryFacet._meta.get_field("choices").get_lookups() or "__" in facet.key or facet.key.lstrip("-").isdecimal() or value not in facet.choices:
                return JsonResponse({"error": "invalid_facet_filter"}, status=400)
            eligible_offers = eligible_offers.filter(**{f"variant__attributes__{facet.key}": value})
    if min_price:
        eligible_offers = eligible_offers.filter(price_toman__gte=min_price)
    if max_price:
        eligible_offers = eligible_offers.filter(price_toman__lte=max_price)
    queryset = Product.objects.filter(pk__in=eligible_offers.values("variant__product_id"))
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(brand__name__icontains=query))
    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)
    if brand_slug:
        queryset = queryset.filter(brand__slug=brand_slug, brand__is_active=True)
    queryset = queryset.defer("description", "specifications").select_related("brand", "category").prefetch_related(Prefetch(
        "media", queryset=ProductMedia.objects.filter(is_approved=True).only("id", "product_id", "alt_text", "position"), to_attr="approved_media"
    )).annotate(starting_price_toman=Min(
        "variants__offers__price_toman", filter=Q(variants__offers__pk__in=eligible_offers.values("pk"))
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
        "image": _image_data(row.approved_media[0] if row.approved_media else None),
    } for row in rows[:24]], "page": page, "has_next": has_next})


@require_GET
def product_detail(_request, slug):
    product = get_object_or_404(
        Product.objects.select_related("brand", "category").prefetch_related(Prefetch(
            "media", queryset=ProductMedia.objects.filter(is_approved=True), to_attr="approved_media"
        )),
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
        "images": [_image_data(media) for media in product.approved_media],
        "category": {"name": product.category.name, "slug": product.category.slug},
        "brand": product.brand.name if product.brand else None, "brand_id": product.brand_id, "offers": offer_rows,
    }})
