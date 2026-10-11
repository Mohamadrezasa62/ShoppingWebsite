import csv
import hashlib
from io import StringIO
from uuid import UUID
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from catalog.models import Offer, Warehouse, StockBalance, StockImportReceipt
from catalog.inventory import InventoryError, balances, change, sync, movement, MAX_STOCK
from operations.api import _reason, _audit
from .views import _auth, _membership
from .inventory_views import authorize_locked
from .import_views import safe_cell

HEADERS = ["sku", "warehouse_code", "quantity", "version"]


@require_http_methods(["GET", "POST"])
@csrf_protect
def inventory_csv(request, seller_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    if request.method == "GET":
        try:
            after = int(request.GET.get("after_id", "0"))
        except ValueError:
            return JsonResponse({"error": "invalid_cursor"}, status=400)
        if not 0 <= after <= 9_000_000_000_000_000_000:
            return JsonResponse({"error": "invalid_cursor"}, status=400)
        rows = list(StockBalance.objects.filter(offer__seller_id=seller_id, pk__gt=after).select_related("offer__variant", "warehouse").order_by("pk")[:501])
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(HEADERS)
        for row in rows[:500]:
            writer.writerow([safe_cell(row.offer.variant.sku), safe_cell(row.warehouse.code), row.quantity, row.version])
        response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="warehouse-stock-after-{after}.csv"'
        response["X-Next-Balance-ID"] = str(rows[499].pk) if len(rows) > 500 else "0"
        response["X-Content-Type-Options"] = "nosniff"
        return response
    reason = _reason(request.POST)
    if not reason or set(request.POST) != {"reason", "request_key"} or set(request.FILES) != {"file"}:
        return JsonResponse({"error": "invalid_inventory_import"}, status=400)
    upload = request.FILES["file"]
    if not 0 < upload.size <= 256 * 1024:
        return JsonResponse({"error": "invalid_inventory_import"}, status=400)
    raw = upload.read(256 * 1024 + 1)
    try:
        if len(raw) > 256 * 1024:
            raise ValueError()
        key = UUID(request.POST["request_key"])
        text = raw.decode("utf-8-sig")
        if "\x00" in text:
            raise ValueError()
        reader = csv.DictReader(StringIO(text), strict=True)
        if reader.fieldnames != HEADERS:
            raise ValueError()
        prepared, seen = [], set()
        for row in reader:
            if len(prepared) >= 500 or set(row) != set(HEADERS) or any(value is None for value in row.values()):
                raise ValueError()
            sku, code = row["sku"].strip(), row["warehouse_code"].strip()
            quantity, version = int(row["quantity"]), int(row["version"])
            if not 1 <= len(sku) <= 80 or not 1 <= len(code) <= 80 or (sku, code) in seen or not 0 <= quantity <= MAX_STOCK or not 0 <= version <= 9_000_000_000_000_000_000:
                raise ValueError()
            seen.add((sku, code))
            prepared.append((sku, code, quantity, version))
        if not prepared:
            raise ValueError()
    except (ValueError, UnicodeDecodeError, csv.Error):
        return JsonResponse({"error": "invalid_inventory_import"}, status=400)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        with transaction.atomic():
            seller = authorize_locked(request.user, seller_id)
            existing = StockImportReceipt.objects.filter(seller=seller, request_key=key).first()
            if existing:
                if existing.digest != digest or existing.actor_id != request.user.pk:
                    raise InventoryError("inventory_import_conflict")
                return JsonResponse({"updated": existing.updated_count})
            offers = {row.variant.sku: row for row in Offer.objects.select_for_update(of=("self",)).filter(seller=seller, variant__sku__in=[row[0] for row in prepared]).select_related("variant").order_by("pk")}
            warehouses = {row.code: row for row in Warehouse.objects.select_for_update().filter(seller=seller, code__in=[row[1] for row in prepared], is_active=True).order_by("pk")}
            if any(sku not in offers or code not in warehouses for sku, code, _, _ in prepared) or any(not offer.inventory_managed for offer in offers.values()):
                raise InventoryError("inventory_import_reference_conflict")
            all_balances = {offer.pk: balances(offer) for offer in sorted(offers.values(), key=lambda row: row.pk)}
            for sku, code, quantity, version in prepared:
                offer, warehouse = offers[sku], warehouses[code]
                rows = all_balances[offer.pk]
                balance = next((row for row in rows if row.warehouse_id == warehouse.pk), None)
                if balance is None:
                    if version != 0:
                        raise InventoryError("stock_version_conflict")
                    balance = StockBalance.objects.create(offer=offer, warehouse=warehouse)
                    rows.append(balance)
                elif balance.version != version:
                    raise InventoryError("stock_version_conflict")
                if quantity < balance.reserved_quantity:
                    raise InventoryError("stock_below_reserved_or_capacity")
                delta = quantity - balance.quantity
                change(balance, quantity=delta)
                movement(balance, "import_adjustment", delta, 0, f"inventory-import:{seller.pk}:{key}:{balance.pk}", actor=request.user, reason=reason)
            for offer in offers.values():
                sync(offer, all_balances[offer.pk])
            receipt = StockImportReceipt.objects.create(seller=seller, actor=request.user, request_key=key, digest=digest, updated_count=len(prepared))
            _audit(request, "warehouse_stock_imported", "stock_import", receipt.pk, reason, {}, {"seller_id": seller.pk, "updated_count": len(prepared)})
    except InventoryError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    return JsonResponse({"updated": len(prepared)})
