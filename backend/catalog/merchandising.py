from django.db.models import Min, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET
from .api import visible_offers, _image_data
from .models import Product, ProductCollection, ProductMedia
from .question_api import public_product


def active_collections():
    now = timezone.now()
    return ProductCollection.objects.filter(is_published=True).filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now)).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))


def cards(rows, limit=50):
    offers = visible_offers()
    rows = rows.filter(pk__in=offers.values("variant__product_id")).only("id", "title", "slug").prefetch_related(Prefetch("media", queryset=ProductMedia.objects.filter(is_approved=True).only("id", "product_id", "alt_text", "position"), to_attr="approved_media")).annotate(price=Min("variants__offers__price_toman", filter=Q(variants__offers__pk__in=offers.values("pk")))).order_by("pk")[:limit]
    return [{"id": row.pk, "title": row.title, "slug": row.slug, "price_toman": row.price, "image": _image_data(row.approved_media[0] if row.approved_media else None)} for row in rows]


@require_GET
def collections(request):
    return JsonResponse({"collections": [{"title": row.title, "slug": row.slug, "description": row.description} for row in active_collections().order_by("-updated_at")[:50]]})


@require_GET
def collection(request, slug):
    row = get_object_or_404(active_collections(), slug=slug)
    return JsonResponse({"collection": {"title": row.title, "slug": row.slug, "description": row.description, "products": cards(row.products.all())}})


@require_GET
def related(request, product_id):
    product = public_product(product_id)
    return JsonResponse({"products": cards(Product.objects.filter(category_id=product.category_id).exclude(pk=product.pk), limit=8), "basis": "same_category"})
