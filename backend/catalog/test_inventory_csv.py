import csv
from io import StringIO
from unittest.mock import patch
from uuid import uuid4
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from . import test_inventory as fixtures
from .models import StockBalance, StockImportReceipt, StockMovement
from operations.models import Notification, OutboxEvent
from operations.events import process_event


class InventoryCsvTests(TestCase):
    post = fixtures.WarehouseInventoryTests.post

    def setUp(self):
        fixtures.WarehouseInventoryTests.setUp(self)
        fixtures.WarehouseInventoryTests.initialize(self)
        self.path = self.base + "inventory-csv/"

    def rows(self):
        return [[self.offer.variant.sku, row.warehouse.code, row.quantity + 2, row.version] for row in StockBalance.objects.filter(offer=self.offer).select_related("warehouse").order_by("pk")]

    def csv(self, rows):
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["sku", "warehouse_code", "quantity", "version"])
        writer.writerows(rows)
        return output.getvalue().encode()

    def upload(self, raw, key=None):
        return self.client.post(self.path, {"file": SimpleUploadedFile("inventory.csv", raw, content_type="text/csv"), "request_key": str(key or uuid4()), "reason": "Warehouse recount"})

    def test_import_is_versioned_atomic_and_idempotent(self):
        raw, key = self.csv(self.rows()), uuid4()
        self.assertEqual(self.upload(raw, key).status_code, 200)
        self.assertEqual(self.upload(raw, key).status_code, 200)
        self.assertEqual(StockImportReceipt.objects.count(), 1)
        self.assertEqual(StockMovement.objects.filter(kind="import_adjustment").count(), 2)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.available_quantity, 8)
        self.assertEqual(self.upload(self.csv(self.rows()), key).status_code, 409)

    def test_late_row_conflict_rolls_back_earlier_rows_and_audit_failure(self):
        rows = self.rows()
        rows[-1][-1] -= 1
        self.assertEqual(self.upload(self.csv(rows)).status_code, 409)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.available_quantity, 4)
        self.assertFalse(StockMovement.objects.filter(kind="import_adjustment").exists())
        self.assertFalse(StockImportReceipt.objects.exists())
        with patch("sellers.inventory_csv._audit", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.upload(self.csv(self.rows()))
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.available_quantity, 4)
        self.assertFalse(StockImportReceipt.objects.exists())

    def test_csv_does_not_overwrite_a_new_checkout_reservation(self):
        raw = self.csv(self.rows())
        fixtures.WarehouseInventoryTests.checkout(self)
        self.assertEqual(self.upload(raw).status_code, 409)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.reserved_quantity, 3)
        self.assertEqual(self.offer.available_quantity, 4)

    def test_input_bounds_unknown_references_and_csrf(self):
        rows = self.rows()
        for raw in (b"bad\nheader", self.csv([rows[0], rows[0]]), self.csv([rows[0]] * 501), b"\x00", b"x" * (256 * 1024 + 1)):
            self.assertEqual(self.upload(raw).status_code, 400)
        self.assertEqual(self.upload(self.csv([["FOREIGN-SKU", "default", 1, 0]])).status_code, 409)
        self.assertEqual(self.upload(self.csv([[self.offer.variant.sku, "foreign-warehouse", 1, 0]])).status_code, 409)
        self.client.force_login(self.user)
        self.assertEqual(self.upload(self.csv(rows)).status_code, 404)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.path, {"file": SimpleUploadedFile("a.csv", self.csv(rows))}).status_code, 403)

    def test_export_is_private_and_spreadsheet_safe(self):
        variant = self.offer.variant
        variant.sku = "=FORMULA"
        variant.save(update_fields=["sku"])
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0], ["sku", "warehouse_code", "quantity", "version"])
        self.assertEqual(rows[1][0], "'=FORMULA")
        self.assertEqual(response["X-Next-Balance-ID"], "0")
        self.assertEqual(self.client.get(self.path, {"after_id": "bad"}).status_code, 400)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.path).status_code, 404)

    def test_low_stock_event_is_private_deduplicated_and_suppresses_stale_stock(self):
        balance = StockBalance.objects.get(offer=self.offer, warehouse=self.primary)
        data = {"warehouse_id": self.primary.pk, "quantity": 10, "version": balance.version, "reason": "Replenish stock"}
        self.assertEqual(self.post(f"inventory/{self.offer.pk}/adjust/", data).status_code, 200)
        fixtures.WarehouseInventoryTests.checkout(self, quantity=9)
        event = OutboxEvent.objects.get(topic="seller.stock_low")
        self.assertTrue(process_event(event.pk))
        self.assertFalse(process_event(event.pk))
        self.assertEqual(Notification.objects.filter(user=self.owner).count(), 1)
        self.assertFalse(Notification.objects.filter(user=self.user).exists())
        self.assertEqual(Notification.objects.get().link, "/seller-panel/")
        balance.refresh_from_db()
        self.assertEqual(self.post(f"inventory/{self.offer.pk}/adjust/", {**data, "quantity": 20, "version": balance.version}).status_code, 200)
        fixtures.WarehouseInventoryTests.checkout(self, quantity=10)
        latest = OutboxEvent.objects.filter(topic="seller.stock_low").order_by("-pk").first()
        self.assertNotEqual(latest.pk, event.pk)
        balance.refresh_from_db()
        self.assertEqual(self.post(f"inventory/{self.offer.pk}/adjust/", {**data, "quantity": 30, "version": balance.version}).status_code, 200)
        self.assertTrue(process_event(latest.pk))
        self.assertEqual(Notification.objects.count(), 1)
