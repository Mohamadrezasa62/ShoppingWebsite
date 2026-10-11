import csv
import io
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from catalog.models import Offer
from catalog.inventory import InventoryError, set_total_locked
from operations.models import AuditEvent
from .models import Seller
from .views import _auth, _membership

FIELDS = ["sku", "price_toman", "available_quantity", "status", "warranty"]


def safe_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@require_http_methods(["GET", "POST"])
@csrf_protect
def offers_csv(request, seller_id):
    if error := _auth(request):
        return error
    membership = _membership(request, seller_id)
    if membership.seller.status != Seller.Status.APPROVED:
        return JsonResponse({"error": "seller_approval_required"}, status=403)
    if request.method == "GET":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(FIELDS)
        for row in Offer.objects.filter(seller_id=seller_id).select_related("variant").order_by("pk")[:10000]:
            writer.writerow([safe_cell(row.variant.sku), row.price_toman, row.available_quantity, row.status, safe_cell(row.warranty)])
        response = HttpResponse("\ufeff" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="offers.csv"'
        return response
    upload = request.FILES.get("file")
    if not upload or upload.size > 256 * 1024:
        return JsonResponse({"error": "invalid_import_file"}, status=400)
    try:
        reader = csv.DictReader(io.StringIO(upload.read().decode("utf-8-sig")))
        if reader.fieldnames != FIELDS:
            raise ValueError("invalid_columns")
        rows = list(reader)
        if not 1 <= len(rows) <= 1000:
            raise ValueError("invalid_row_count")
        seen = set()
        prepared = []
        for number, row in enumerate(rows, 2):
            sku = row["sku"]
            if sku in seen or not sku or None in row or any(value is None for value in row.values()):
                raise ValueError(f"invalid_row:{number}")
            seen.add(sku)
            price, stock = int(row["price_toman"]), int(row["available_quantity"])
            if not 1 <= price <= 9_000_000_000_000_000_000 or not 0 <= stock <= 2_147_483_647 or row["status"] not in ("active", "paused") or len(row["warranty"]) > 200:
                raise ValueError(f"invalid_row:{number}")
            prepared.append((sku, price, stock, row["status"], row["warranty"]))
        with transaction.atomic():
            from .inventory_views import authorize_locked
            authorize_locked(request.user, seller_id)
            offers = {offer.variant.sku: offer for offer in Offer.objects.select_for_update(of=("self",)).filter(seller_id=seller_id, variant__sku__in=seen).select_related("variant__product__category", "variant__product__brand", "seller").order_by("pk")}
            if len(offers) != len(prepared):
                raise ValueError("unknown_seller_sku")
            from commerce.helpers import offer_is_visible
            for sku, price, stock, status, warranty in prepared:
                offer = offers[sku]
                if stock < offer.reserved_quantity or offer.status in ("pending_review", "rejected"):
                    raise ValueError("stock_or_moderation_conflict")
                before = {"price_toman": offer.price_toman, "available_quantity": offer.available_quantity, "status": offer.status}
                set_total_locked(offer, stock, request.user, "Validated seller CSV import")
                offer.price_toman, offer.status, offer.warranty = price, status, warranty
                if status == "active" and not offer_is_visible(offer):
                    raise ValueError("offer_not_publishable")
                offer.save()
                AuditEvent.objects.create(actor=request.user, action="seller_offer_import", target_type="offer", target_id=str(offer.pk), reason="Validated seller CSV import", before=before, after={"price_toman": price, "available_quantity": stock, "status": status})
    except (UnicodeDecodeError, csv.Error, ValueError, KeyError, TypeError, InventoryError) as error:
        return JsonResponse({"error": "import_rejected", "details": error.code if isinstance(error, InventoryError) else str(error)}, status=400)
    return JsonResponse({"updated": len(prepared)})
