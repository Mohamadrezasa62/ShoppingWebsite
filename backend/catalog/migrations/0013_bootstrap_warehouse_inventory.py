from django.db import migrations
from django.utils import timezone


def bootstrap(apps, schema_editor):
    alias = schema_editor.connection.alias
    Offer = apps.get_model("catalog", "Offer")
    Warehouse = apps.get_model("catalog", "Warehouse")
    Balance = apps.get_model("catalog", "StockBalance")
    Reservation = apps.get_model("catalog", "StockReservation")
    Movement = apps.get_model("catalog", "StockMovement")
    Line = apps.get_model("commerce", "OrderLine")
    for offer in Offer.objects.using(alias).filter(inventory_managed=False).order_by("pk").iterator():
        if not 0 <= offer.reserved_quantity <= offer.available_quantity <= 2_147_483_647:
            raise RuntimeError(f"Inventory bootstrap blocked: invalid stock for offer {offer.pk}")
        pending = list(Line.objects.using(alias).filter(offer_id=offer.pk, delivery__order__status="pending_payment").order_by("pk"))
        if sum(line.quantity for line in pending) != offer.reserved_quantity:
            raise RuntimeError(f"Inventory bootstrap blocked: reservation mismatch for offer {offer.pk}")
        warehouse, _ = Warehouse.objects.using(alias).get_or_create(seller_id=offer.seller_id, is_default=True, defaults={"code": "default", "name": "انبار اصلی"})
        balance = Balance.objects.using(alias).create(offer_id=offer.pk, warehouse_id=warehouse.pk, quantity=offer.available_quantity, reserved_quantity=offer.reserved_quantity)
        Movement.objects.using(alias).create(balance_id=balance.pk, kind="bootstrap", quantity_delta=balance.quantity, reserved_delta=balance.reserved_quantity, event_key=f"inventory:{offer.pk}:bootstrap", reason="Warehouse inventory migration from validated legacy totals")
        Reservation.objects.using(alias).bulk_create([Reservation(order_line_id=line.pk, balance_id=balance.pk, quantity=line.quantity) for line in pending])
        Offer.objects.using(alias).filter(pk=offer.pk).update(inventory_managed=True, inventory_activated_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [("catalog", "0012_offer_inventory_activated_at_offer_inventory_managed_and_more")]
    operations = [migrations.RunPython(bootstrap)]
