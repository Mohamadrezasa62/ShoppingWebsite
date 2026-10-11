from uuid import UUID
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from catalog.models import Offer, Warehouse, StockBalance, StockMovement
from catalog.inventory import InventoryError, MAX_STOCK, activate_locked, balances, sync, change, movement
from operations.api import _reason, _audit
from .models import Seller, SellerMembership
from .views import _auth, _membership, _data


def warehouse_data(row):
    return {"id": row.pk, "name": row.name, "code": row.code, "active": row.is_active, "default": row.is_default}


def authorize_locked(user, seller_id, owner=False):
    user = get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
    seller = get_object_or_404(Seller.objects.select_for_update(), pk=seller_id)
    member = SellerMembership.objects.filter(seller=seller, user=user).first()
    if not user.is_active or member is None or (owner and member.role != "owner") or seller.status != "approved":
        raise InventoryError("seller_approval_required", 403)
    return seller


@require_http_methods(["GET", "POST"])
@csrf_protect
def warehouses(request, seller_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    if request.method == "GET":
        return JsonResponse({"warehouses": [warehouse_data(row) for row in Warehouse.objects.filter(seller_id=seller_id).order_by("pk")[:20]]})
    data = _data(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"name", "code", "reason"} or not isinstance(data["name"], str) or "\x00" in data["name"] or not 3 <= len(data["name"].strip()) <= 160 or not isinstance(data["code"], str) or data["code"] == "default":
        return JsonResponse({"error": "invalid_warehouse"}, status=400)
    from django.core.validators import validate_slug
    from django.core.exceptions import ValidationError
    try:
        if not 1 <= len(data["code"]) <= 80:
            raise ValidationError("Invalid code")
        validate_slug(data["code"])
    except ValidationError:
        return JsonResponse({"error": "invalid_warehouse_code"}, status=400)
    try:
        with transaction.atomic():
            seller = authorize_locked(request.user, seller_id, owner=True)
            count = seller.warehouses.count()
            if (count >= 19 and not seller.warehouses.filter(is_default=True).exists()) or count >= 20:
                raise InventoryError("warehouse_limit")
            row = Warehouse.objects.create(seller=seller, name=data["name"].strip(), code=data["code"])
            _audit(request, "warehouse_created", "warehouse", row.pk, reason, {}, warehouse_data(row))
    except InventoryError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    except IntegrityError:
        return JsonResponse({"error": "warehouse_code_conflict"}, status=409)
    return JsonResponse({"warehouse": warehouse_data(row)}, status=201)


@require_http_methods(["PATCH"])
@csrf_protect
def warehouse(request, seller_id, warehouse_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    data = _data(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"name", "active", "reason"} or type(data["active"]) is not bool or not isinstance(data["name"], str) or "\x00" in data["name"] or not 3 <= len(data["name"].strip()) <= 160:
        return JsonResponse({"error": "invalid_warehouse"}, status=400)
    try:
        with transaction.atomic():
            authorize_locked(request.user, seller_id, owner=True)
            # Same Offer-before-Warehouse order as commerce; prevent a restock
            # committing into a warehouse deactivated from an older snapshot.
            list(Offer.objects.select_for_update().filter(pk__in=StockBalance.objects.filter(warehouse_id=warehouse_id, warehouse__seller_id=seller_id).values("offer_id")).order_by("pk").values_list("pk", flat=True))
            row = get_object_or_404(Warehouse.objects.select_for_update(), pk=warehouse_id, seller_id=seller_id)
            if not data["active"] and (row.is_default or row.balances.filter(quantity__gt=0).exists()):
                raise InventoryError("warehouse_has_stock_or_default")
            before = warehouse_data(row)
            row.name, row.is_active = data["name"].strip(), data["active"]
            row.save(update_fields=["name", "is_active"])
            _audit(request, "warehouse_updated", "warehouse", row.pk, reason, before, warehouse_data(row))
    except InventoryError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    return JsonResponse({"warehouse": warehouse_data(row)})


@require_http_methods(["GET"])
def inventory(request, seller_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    try:
        after = int(request.GET.get("after_id", "0"))
    except ValueError:
        return JsonResponse({"error": "invalid_cursor"}, status=400)
    if not 0 <= after <= 9_000_000_000_000_000_000:
        return JsonResponse({"error": "invalid_cursor"}, status=400)
    return JsonResponse(inventory_payload(seller_id, after))


def inventory_payload(seller_id, after=0):
    rows = list(Offer.objects.filter(seller_id=seller_id, pk__gt=after).select_related("variant__product").prefetch_related("stock_balances__warehouse").order_by("pk")[:26])
    return {"offers": [{"id": row.pk, "sku": row.variant.sku, "product": row.variant.product.title, "managed": row.inventory_managed, "quantity": row.available_quantity, "reserved": row.reserved_quantity, "balances": [{"id": balance.pk, "warehouse_id": balance.warehouse_id, "warehouse": balance.warehouse.name, "quantity": balance.quantity, "reserved": balance.reserved_quantity, "free": balance.quantity - balance.reserved_quantity, "version": balance.version} for balance in row.stock_balances.all()]} for row in rows[:25]], "next_after_id": rows[24].pk if len(rows) > 25 else None}


@require_http_methods(["POST"])
@csrf_protect
def activate(request, seller_id, offer_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    data = _data(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"reason"}:
        return JsonResponse({"error": "reason_required"}, status=400)
    try:
        with transaction.atomic():
            authorize_locked(request.user, seller_id)
            offer = get_object_or_404(Offer.objects.select_for_update(), pk=offer_id, seller_id=seller_id)
            before = {"managed": offer.inventory_managed}
            activate_locked(offer, request.user)
            if not before["managed"]:
                _audit(request, "warehouse_inventory_activated", "offer", offer.pk, reason, before, {"managed": True})
    except InventoryError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    return JsonResponse({"managed": True})


@require_http_methods(["POST"])
@csrf_protect
def adjust(request, seller_id, offer_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    data = _data(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"warehouse_id", "quantity", "version", "reason"} or any(type(data[key]) is not int for key in ("warehouse_id", "quantity", "version")) or not 0 <= data["quantity"] <= MAX_STOCK or data["version"] < 0:
        return JsonResponse({"error": "invalid_stock_adjustment"}, status=400)
    try:
        with transaction.atomic():
            authorize_locked(request.user, seller_id)
            offer = get_object_or_404(Offer.objects.select_for_update(), pk=offer_id, seller_id=seller_id)
            if not offer.inventory_managed:
                raise InventoryError("activate_inventory_first")
            rows = balances(offer)
            warehouse = get_object_or_404(Warehouse.objects.select_for_update(), pk=data["warehouse_id"], seller_id=seller_id, is_active=True)
            row = next((item for item in rows if item.warehouse_id == warehouse.pk), None)
            if row is None:
                if data["version"] != 0:
                    raise InventoryError("stock_version_conflict")
                row = StockBalance.objects.create(offer=offer, warehouse=warehouse)
                rows.append(row)
            elif row.version != data["version"]:
                raise InventoryError("stock_version_conflict")
            if data["quantity"] < row.reserved_quantity or offer.available_quantity + data["quantity"] - row.quantity > MAX_STOCK:
                raise InventoryError("stock_below_reserved_or_capacity")
            delta = data["quantity"] - row.quantity
            before = {"quantity": row.quantity, "version": row.version}
            change(row, quantity=delta)
            movement(row, "adjustment", delta, 0, f"balance:{row.pk}:version:{row.version}", actor=request.user, reason=reason)
            sync(offer, rows)
            _audit(request, "warehouse_stock_adjusted", "balance", row.pk, reason, before, {"quantity": row.quantity, "version": row.version})
    except InventoryError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    return JsonResponse({"version": row.version})


@require_http_methods(["POST"])
@csrf_protect
def transfer(request, seller_id, offer_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    data = _data(request)
    reason = _reason(data) if data else None
    fields = {"source_id", "destination_id", "quantity", "request_key", "reason"}
    if not reason or set(data) != fields or any(type(data[key]) is not int for key in ("source_id", "destination_id", "quantity")) or not 1 <= data["quantity"] <= MAX_STOCK or data["source_id"] == data["destination_id"]:
        return JsonResponse({"error": "invalid_stock_transfer"}, status=400)
    try:
        key = UUID(str(data["request_key"]))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"error": "invalid_request_key"}, status=400)
    try:
        with transaction.atomic():
            authorize_locked(request.user, seller_id)
            offer = get_object_or_404(Offer.objects.select_for_update(), pk=offer_id, seller_id=seller_id)
            if not offer.inventory_managed:
                raise InventoryError("activate_inventory_first")
            rows = balances(offer)
            warehouses = {row.pk: row for row in Warehouse.objects.select_for_update().filter(pk__in=(data["source_id"], data["destination_id"]), seller_id=seller_id).order_by("pk")}
            if len(warehouses) != 2:
                raise InventoryError("warehouse_not_found", 404)
            event = f"stock-transfer:{offer.pk}:{key}"
            existing = list(StockMovement.objects.filter(event_key__in=(f"{event}:out", f"{event}:in")).select_related("balance"))
            if existing:
                out = next((item for item in existing if item.kind == "transfer_out"), None)
                incoming = next((item for item in existing if item.kind == "transfer_in"), None)
                if len(existing) != 2 or out is None or incoming is None or out.balance.warehouse_id != data["source_id"] or incoming.balance.warehouse_id != data["destination_id"] or incoming.quantity_delta != data["quantity"] or out.actor_id != request.user.pk:
                    raise InventoryError("stock_transfer_conflict")
                return JsonResponse({"transferred": True})
            if any(not row.is_active for row in warehouses.values()):
                raise InventoryError("warehouse_unavailable")
            source = next((row for row in rows if row.warehouse_id == data["source_id"]), None)
            if source is None or source.quantity - source.reserved_quantity < data["quantity"]:
                raise InventoryError("insufficient_free_stock")
            destination = next((row for row in rows if row.warehouse_id == data["destination_id"]), None)
            if destination is None:
                destination = StockBalance.objects.create(offer=offer, warehouse_id=data["destination_id"])
                rows.append(destination)
            change(source, quantity=-data["quantity"])
            change(destination, quantity=data["quantity"])
            movement(source, "transfer_out", -data["quantity"], 0, f"{event}:out", actor=request.user, reason=reason)
            movement(destination, "transfer_in", data["quantity"], 0, f"{event}:in", actor=request.user, reason=reason)
            sync(offer, rows)
            _audit(request, "warehouse_stock_transferred", "offer", offer.pk, reason, {}, {"source_id": data["source_id"], "destination_id": data["destination_id"], "quantity": data["quantity"]})
    except InventoryError as error:
        return JsonResponse({"error": error.code}, status=error.status)
    return JsonResponse({"transferred": True})


@require_http_methods(["GET"])
def history(request, seller_id, offer_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    get_object_or_404(Offer, pk=offer_id, seller_id=seller_id)
    rows = StockMovement.objects.filter(balance__offer_id=offer_id).select_related("balance__warehouse").order_by("-pk")[:100]
    return JsonResponse({"movements": [{"id": row.pk, "warehouse": row.balance.warehouse.name, "kind": row.kind, "quantity_delta": row.quantity_delta, "reserved_delta": row.reserved_delta, "reason": row.reason, "created_at": row.created_at.isoformat()} for row in rows]})
