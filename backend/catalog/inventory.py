"""Offer locks serialize physical balances, allocation and cached public totals.

StockBalance is authoritative for managed offers. Offer quantities remain cached
aggregates for catalog filtering; legacy unactivated offers retain their old path.
"""
from uuid import uuid4
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from commerce.models import OrderLine
from .models import Offer, Warehouse, StockBalance, StockReservation, StockMovement

MAX_STOCK = 2_147_483_647


class InventoryError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status


def balances(offer):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Inventory requires a caller transaction and locked offer")
    rows = list(StockBalance.objects.select_for_update(of=("self",)).filter(offer=offer).select_related("warehouse").order_by("pk"))
    if not rows or offer.inventory_activated_at is None or sum(row.quantity for row in rows) != offer.available_quantity or sum(row.reserved_quantity for row in rows) != offer.reserved_quantity or any(row.warehouse.seller_id != offer.seller_id or row.reserved_quantity > row.quantity or (not row.warehouse.is_active and row.quantity) for row in rows):
        raise InventoryError("inventory_inconsistent")
    return rows


def sync(offer, rows):
    previous_free = offer.available_quantity - offer.reserved_quantity
    quantity = sum(row.quantity for row in rows)
    reserved = sum(row.reserved_quantity for row in rows)
    if not 0 <= reserved <= quantity <= MAX_STOCK:
        raise InventoryError("inventory_capacity_exceeded")
    offer.available_quantity, offer.reserved_quantity = quantity, reserved
    Offer.objects.filter(pk=offer.pk).update(available_quantity=quantity, reserved_quantity=reserved, updated_at=timezone.now())
    if previous_free > 5 and quantity - reserved <= 5:
        from operations.events import emit
        revision = sum(row.version for row in rows)
        emit(f"stock-low:{offer.pk}:{revision}", "seller.stock_low", offer_id=offer.pk, seller_id=offer.seller_id)


def movement(balance, kind, quantity, reserved, key, line=None, actor=None, reason="Commerce inventory transition"):
    StockMovement.objects.create(balance=balance, kind=kind, quantity_delta=quantity, reserved_delta=reserved, event_key=key, order_line=line, actor=actor, reason=reason)


def change(row, quantity=0, reserved=0):
    row.quantity += quantity
    row.reserved_quantity += reserved
    row.version += 1
    if not 0 <= row.reserved_quantity <= row.quantity <= MAX_STOCK:
        raise InventoryError("inventory_inconsistent")
    row.save(update_fields=["quantity", "reserved_quantity", "version"])


def activate_locked(offer, actor=None):
    if offer.inventory_managed:
        balances(offer)
        return offer
    if not 0 <= offer.reserved_quantity <= offer.available_quantity <= MAX_STOCK or StockBalance.objects.filter(offer=offer).exists():
        raise InventoryError("legacy_inventory_inconsistent")
    pending = list(OrderLine.objects.filter(offer=offer, delivery__order__status="pending_payment").order_by("pk"))
    if sum(line.quantity for line in pending) != offer.reserved_quantity:
        raise InventoryError("legacy_inventory_inconsistent")
    warehouse, _ = Warehouse.objects.get_or_create(seller_id=offer.seller_id, is_default=True, defaults={"name": "انبار اصلی", "code": "default"})
    if not warehouse.is_active:
        raise InventoryError("warehouse_unavailable")
    balance = StockBalance.objects.create(offer=offer, warehouse=warehouse, quantity=offer.available_quantity, reserved_quantity=offer.reserved_quantity)
    movement(balance, "bootstrap", balance.quantity, balance.reserved_quantity, f"inventory:{offer.pk}:bootstrap", actor=actor, reason="Activated warehouse inventory from legacy totals")
    StockReservation.objects.bulk_create([StockReservation(order_line=line, balance=balance, quantity=line.quantity) for line in pending])
    offer.inventory_managed, offer.inventory_activated_at = True, timezone.now()
    offer.save(update_fields=["inventory_managed", "inventory_activated_at"])
    return offer


@transaction.atomic
def activate(offer_id, actor=None):
    if actor is not None:
        actor = get_user_model().objects.select_for_update(no_key=True).get(pk=actor.pk)
    offer = Offer.objects.select_for_update().get(pk=offer_id)
    return activate_locked(offer, actor)


def set_total_locked(offer, quantity, actor=None, reason="Legacy stock update"):
    if not offer.inventory_managed:
        offer.available_quantity = quantity
        return
    rows = balances(offer)
    if quantity == offer.available_quantity:
        return
    if len(rows) != 1 or not rows[0].warehouse.is_default:
        raise InventoryError("warehouse_stock_update_required")
    row = rows[0]
    if quantity < row.reserved_quantity:
        raise InventoryError("stock_below_reserved")
    delta = quantity - row.quantity
    if delta:
        change(row, quantity=delta)
        movement(row, "adjustment", delta, 0, f"stock-adjustment:{uuid4()}", actor=actor, reason=reason)
        sync(offer, rows)


def reserve_line(offer, line):
    if not offer.inventory_managed:
        offer.reserved_quantity += line.quantity
        offer.save(update_fields=["reserved_quantity"])
        return
    rows = balances(offer)
    remaining = line.quantity
    for row in rows:
        if not row.warehouse.is_active:
            continue
        take = min(remaining, row.quantity - row.reserved_quantity)
        if take:
            change(row, reserved=take)
            StockReservation.objects.create(order_line=line, balance=row, quantity=take)
            movement(row, "reserve", 0, take, f"line:{line.pk}:reserve:{row.pk}", line=line)
            remaining -= take
        if remaining == 0:
            break
    if remaining:
        raise InventoryError("offer_unavailable")
    sync(offer, rows)


def allocations(offer, line, status, rows):
    reservations = list(StockReservation.objects.select_for_update().filter(order_line=line).order_by("balance_id"))
    mapped = {row.pk: row for row in rows}
    if sum(row.quantity for row in reservations) != line.quantity or any(row.balance_id not in mapped or row.status != status or row.restocked_quantity > row.quantity for row in reservations):
        raise InventoryError("inventory_allocation_inconsistent")
    return reservations, mapped


def can_consume(offer, line):
    if not offer.inventory_managed:
        return offer.reserved_quantity >= line.quantity and offer.available_quantity >= line.quantity
    try:
        rows = balances(offer)
        reservations, mapped = allocations(offer, line, "reserved", rows)
        return all(mapped[row.balance_id].reserved_quantity >= row.quantity and mapped[row.balance_id].quantity >= row.quantity for row in reservations)
    except InventoryError:
        return False


def finish_line(offer, line, consume):
    if not offer.inventory_managed:
        offer.reserved_quantity -= line.quantity
        if consume:
            offer.available_quantity -= line.quantity
        offer.save(update_fields=["reserved_quantity", "available_quantity"])
        return
    rows = balances(offer)
    reservations, mapped = allocations(offer, line, "reserved", rows)
    for reservation in reservations:
        row = mapped[reservation.balance_id]
        delta = -reservation.quantity if consume else 0
        change(row, quantity=delta, reserved=-reservation.quantity)
        reservation.status = "consumed" if consume else "released"
        reservation.save(update_fields=["status"])
        movement(row, reservation.status, delta, -reservation.quantity, f"line:{line.pk}:{reservation.status}:{row.pk}", line=line)
    sync(offer, rows)


def restock_line(offer, line, positions, event_key):
    if not positions or len(set(positions)) != len(positions) or any(type(value) is not int or not 0 <= value < line.quantity for value in positions):
        raise InventoryError("invalid_restock_positions")
    if not offer.inventory_managed:
        if offer.available_quantity + len(positions) > MAX_STOCK:
            raise InventoryError("inventory_capacity_exceeded")
        offer.available_quantity += len(positions)
        offer.save(update_fields=["available_quantity"])
        return
    rows = balances(offer)
    existing = list(StockMovement.objects.filter(event_key__startswith=f"{event_key}:balance:"))
    reservations = list(StockReservation.objects.filter(order_line=line).order_by("balance_id"))
    additions = {}
    if reservations:
        reservations, mapped = allocations(offer, line, "consumed", rows)
        start = 0
        for reservation in reservations:
            count = sum(start <= position < start + reservation.quantity for position in positions)
            start += reservation.quantity
            if count:
                additions[reservation.balance_id] = count
    else:
        # Historical paid lines predate activation and have no warehouse attribution.
        if line.delivery.order.created_at >= offer.inventory_activated_at:
            raise InventoryError("inventory_allocation_missing")
        warehouse = Warehouse.objects.get(seller_id=offer.seller_id, is_default=True, is_active=True)
        row, created = StockBalance.objects.get_or_create(offer=offer, warehouse=warehouse)
        if created:
            rows.append(row)
        additions[row.pk] = len(positions)
    if existing:
        if {row.balance_id: row.quantity_delta for row in existing} != additions or any(row.order_line_id != line.pk or row.kind not in ("restock", "legacy_restock") for row in existing):
            raise InventoryError("restock_idempotency_conflict")
        return
    for reservation in reservations:
        count = additions.get(reservation.balance_id, 0)
        if reservation.restocked_quantity + count > reservation.quantity:
            raise InventoryError("restock_quantity_exceeded")
        if count:
            reservation.restocked_quantity += count
            reservation.save(update_fields=["restocked_quantity"])
    mapped = {row.pk: row for row in rows}
    for balance_id, count in additions.items():
        row = mapped[balance_id]
        if not row.warehouse.is_active:
            raise InventoryError("warehouse_unavailable")
        change(row, quantity=count)
        movement(row, "restock" if reservations else "legacy_restock", count, 0, f"{event_key}:balance:{row.pk}", line=line)
    sync(offer, rows)
