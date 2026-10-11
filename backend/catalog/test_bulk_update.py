import csv
import json
from io import StringIO
from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone
from operations.events import process_event
from operations.models import AuditEvent, OutboxEvent
from .bulk_import import ImportErrorDetail, submit_import
from .bulk_update import UPDATE_HEADERS, content_revision, parse_update_csv
from .models import Category, Product


class BulkUpdateTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user("09123456501", is_staff=True)
        self.actor.groups.add(Group.objects.create(name="catalog_operator"))
        self.other = get_user_model().objects.create_user("09123456502")
        self.category = Category.objects.create(name="Phones", slug="phones")
        self.products = [Product.objects.create(title=f"Original {n}", slug=f"original-{n}", category=self.category, status="published") for n in range(2)]

    def source(self, products=None):
        result = StringIO()
        writer = csv.writer(result)
        writer.writerow(UPDATE_HEADERS)
        for product in products or self.products:
            writer.writerow([product.pk, content_revision(product), f"Updated {product.pk}", "New plain description", '{"screen":"large"}'])
        return result.getvalue().encode()

    def submit(self, source=None, key=None):
        return submit_import(self.actor, source or self.source(), key or uuid4(), "Reviewed editorial changes", mode="update")

    def test_atomic_success_preserves_publication_identity_and_audits_each_product(self):
        job = self.submit()
        self.assertTrue(process_event(job.last_event_id))
        self.assertFalse(process_event(job.last_event_id))
        job.refresh_from_db()
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.rows, [])
        self.assertEqual(job.product_ids, [p.pk for p in self.products])
        for product in self.products:
            product.refresh_from_db()
            self.assertEqual(product.title, f"Updated {product.pk}")
            self.assertEqual(product.status, "published")
            self.assertEqual(product.category_id, self.category.pk)
            audit = AuditEvent.objects.get(action="catalog_bulk_product_updated", target_id=str(product.pk))
            self.assertTrue(audit.before["title"].startswith("Original"))
            self.assertEqual(audit.after["title"], product.title)

    def test_last_row_revision_conflict_rolls_back_products_and_audits(self):
        job = self.submit()
        Product.objects.filter(pk=self.products[1].pk).update(description="Intervening editor change")
        self.assertTrue(process_event(job.last_event_id))
        job.refresh_from_db()
        self.assertEqual(job.error, {"code": "catalog_revision_conflict", "row": 3})
        self.products[0].refresh_from_db()
        self.products[1].refresh_from_db()
        self.assertTrue(self.products[0].title.startswith("Original"))
        self.assertEqual(self.products[1].description, "Intervening editor change")
        self.assertFalse(AuditEvent.objects.filter(action="catalog_bulk_product_updated").exists())

    def test_publication_or_taxonomy_change_invalidates_pending_file(self):
        job = self.submit()
        Product.objects.filter(pk=self.products[0].pk).update(status="archived")
        self.assertTrue(process_event(job.last_event_id))
        job.refresh_from_db()
        self.assertEqual(job.error["code"], "catalog_revision_conflict")
        self.assertEqual(job.error["row"], 2)

    def test_role_revocation_stops_worker(self):
        job = self.submit()
        self.actor.groups.clear()
        self.assertTrue(process_event(job.last_event_id))
        job.refresh_from_db()
        self.assertEqual(job.error["code"], "authorization_revoked")
        self.products[0].refresh_from_db()
        self.assertTrue(self.products[0].title.startswith("Original"))

    def test_audit_outage_rolls_back_and_event_retry_does_not_duplicate_updates(self):
        job = self.submit()
        with patch("catalog.bulk_update.AuditEvent.objects.create", side_effect=RuntimeError("Audit outage")):
            self.assertFalse(process_event(job.last_event_id))
        self.products[0].refresh_from_db()
        self.assertTrue(self.products[0].title.startswith("Original"))
        job.refresh_from_db()
        self.assertEqual(job.status, "queued")
        OutboxEvent.objects.filter(pk=job.last_event_id).update(available_at=timezone.now())
        self.assertTrue(process_event(job.last_event_id))
        self.assertEqual(AuditEvent.objects.filter(action="catalog_bulk_product_updated").count(), 2)

    def test_replay_is_same_job_and_changed_source_conflicts(self):
        key, source = uuid4(), self.source()
        job = self.submit(source, key)
        self.assertTrue(process_event(job.last_event_id))
        self.assertEqual(self.submit(source, key).pk, job.pk)
        with self.assertRaises(ImportErrorDetail):
            self.submit(source.replace(b"New plain", b"Changed plain"), key)
        self.assertEqual(OutboxEvent.objects.count(), 1)

    def test_parser_rejects_duplicate_unknown_format_and_invalid_revision(self):
        for raw in [self.source([self.products[0], self.products[0]]), self.source().replace(b"product_id", b"sku"), self.source().replace(content_revision(self.products[0]).encode(), b"invalid"), self.source().replace(b"New plain", b"Bad\x00plain"), self.source().replace(b'""screen"":""large""', b'""screen"":5'), b"x" * (1024*1024+1)]:
            with self.assertRaises(ImportErrorDetail):
                parse_update_csv(raw)

    def test_private_revision_export_submission_and_csrf(self):
        path = "/api/v1/operations/catalog-imports/"
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(path+"update-export/").status_code, 403)
        self.client.force_login(self.actor)
        self.products[0].title = "=formula"
        self.products[0].save()
        exported = self.client.get(path+"update-export/")
        rows = list(csv.DictReader(StringIO(exported.content.decode())))
        self.assertEqual(tuple(rows[0]), UPDATE_HEADERS)
        self.assertEqual(rows[0]["title"], "'=formula")
        self.assertEqual(rows[0]["revision"], content_revision(self.products[0]))
        self.assertEqual(exported["X-Next-Product-ID"], "0")
        self.assertEqual(self.client.get(path+"update-export/?after_id=bad").status_code, 400)
        response = self.client.post(path, {"mode": "update", "reason": "Reviewed edits", "idempotency_key": str(uuid4()), "file": SimpleUploadedFile("updates.csv", self.source())})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["import"]["mode"], "update")
        self.assertNotIn("rows", response.json()["import"])
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        self.assertEqual(client.post(path, {}).status_code, 403)
