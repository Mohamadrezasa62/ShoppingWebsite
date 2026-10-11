from django.db.models import Min, Prefetch, Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .api import visible_offers, _image_data
from .models import Product, ProductMedia


@require_GET
def compare(request):
    raw = request.GET.get("ids", "")
    if len(raw) > 100:
        return JsonResponse({"error": "invalid_comparison"}, status=400)
    try:
        ids = [int(value) for value in raw.split(",")]
    except ValueError:
        return JsonResponse({"error": "invalid_comparison"}, status=400)
    if not 2 <= len(ids) <= 4 or len(set(ids)) != len(ids) or any(not 1 <= value <= 9_000_000_000_000_000_000 for value in ids):
        return JsonResponse({"error": "invalid_comparison"}, status=400)
    offers = visible_offers()
    products = Product.objects.filter(pk__in=ids).filter(pk__in=offers.values("variant__product_id"))
    products = products.select_related("brand", "category").defer("description").annotate(price=Min("variants__offers__price_toman", filter=Q(variants__offers__pk__in=offers.values("pk")))).prefetch_related(Prefetch("media", queryset=ProductMedia.objects.filter(is_approved=True).only("id", "product_id", "alt_text", "position"), to_attr="approved_media"))
    mapped = {row.pk: row for row in products}
    if len(mapped) != len(ids):
        return JsonResponse({"error": "comparison_unavailable"}, status=404)
    result = []
    for pk in ids:
        row = mapped[pk]
        specs = {key: value for key, value in list(row.specifications.items())[:50] if isinstance(key, str) and isinstance(value, str) and 1 <= len(key) <= 80 and len(value) <= 500} if isinstance(row.specifications, dict) else {}
        result.append({"id": pk, "slug": row.slug, "title": row.title, "category": row.category.name, "brand": row.brand.name if row.brand else None, "starting_price_toman": row.price, "specifications": specs, "image": _image_data(row.approved_media[0] if row.approved_media else None)})
    return JsonResponse({"products": result, "specification_keys": list(dict.fromkeys(key for row in result for key in row["specifications"]))})
