import csv
from io import StringIO
from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone
from operations.events import process_event
from operations.models import OutboxEvent
from .bulk_import import HEADERS, ImportErrorDetail, parse_csv, submit_import, retry_import
from .models import CatalogImportJob, Category, Product, Variant


class BulkImportTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user("09123456601", is_staff=True)
        self.group = Group.objects.create(name="catalog_operator")
        self.actor.groups.add(self.group)
        self.other = get_user_model().objects.create_user("09123456602")
        self.category = Category.objects.create(name="Phones", slug="phones")

    def source(self, entries=None):
        result = StringIO()
        writer = csv.writer(result)
        writer.writerow(HEADERS)
        for slug, sku in entries or [("import-one", "IMPORT-ONE"), ("import-two", "IMPORT-TWO")]:
            writer.writerow([f"Product {slug}", slug, "phones", "", sku, "Plain description", '{"color":"black"}', '{"screen":"large"}'])
        return result.getvalue().encode()

    def test_success_creates_only_drafts_atomically_and_releases_source_payload(self):
        job = submit_import(self.actor, self.source(), uuid4(), "Approved catalog import")
        self.assertTrue(process_event(job.last_event_id))
        self.assertFalse(process_event(job.last_event_id))
        job.refresh_from_db()
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.rows, [])
        self.assertEqual(len(job.product_ids), 2)
        self.assertEqual(Product.objects.filter(status="draft").count(), 2)
        self.assertEqual(Variant.objects.count(), 2)
        with self.assertRaises(ImportErrorDetail):
            retry_import(self.actor, job.pk, "Repeat import")

    def test_conflicting_later_row_rolls_back_entire_file(self):
        product = Product.objects.create(title="Existing", slug="existing", category=self.category)
        Variant.objects.create(product=product, sku="TAKEN")
        job = submit_import(self.actor, self.source([("new-one", "NEW-ONE"), ("new-two", "TAKEN")]), uuid4(), "Approved import")
        self.assertTrue(process_event(job.last_event_id))
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error, {"code": "catalog_conflict", "row": 3})
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Variant.objects.count(), 1)
        self.assertEqual(job.product_ids, [])

    def test_invalid_reference_can_be_repaired_and_retried_with_new_generation(self):
        self.category.is_active = False
        self.category.save(update_fields=["is_active"])
        job = submit_import(self.actor, self.source(), uuid4(), "Approved import")
        first_event = job.last_event_id
        self.assertTrue(process_event(first_event))
        job.refresh_from_db()
        self.assertEqual(job.error["code"], "invalid_catalog_reference")
        self.category.is_active = True
        self.category.save(update_fields=["is_active"])
        job = retry_import(self.actor, job.pk, "Category restored")
        self.assertEqual(job.attempt, 2)
        self.assertNotEqual(job.last_event_id, first_event)
        self.assertTrue(process_event(job.last_event_id))
        self.assertEqual(Product.objects.count(), 2)
        self.assertFalse(process_event(first_event))

    def test_revoked_role_prevents_background_publication(self):
        job = submit_import(self.actor, self.source(), uuid4(), "Approved import")
        self.actor.groups.clear()
        self.assertTrue(process_event(job.last_event_id))
        job.refresh_from_db()
        self.assertEqual(job.error["code"], "authorization_revoked")
        self.assertFalse(Product.objects.exists())

    def test_unexpected_failure_rolls_back_and_outbox_retry_is_safe(self):
        job = submit_import(self.actor, self.source(), uuid4(), "Approved import")
        with patch.object(Variant, "save", side_effect=RuntimeError("Temporary outage")):
            self.assertFalse(process_event(job.last_event_id))
        self.assertFalse(Product.objects.exists())
        job.refresh_from_db()
        self.assertEqual(job.status, "queued")
        OutboxEvent.objects.filter(pk=job.last_event_id).update(available_at=timezone.now())
        self.assertTrue(process_event(job.last_event_id))
        self.assertEqual(Product.objects.count(), 2)

    def test_idempotency_rejects_changed_source_without_duplicate_events(self):
        key = uuid4()
        job = submit_import(self.actor, self.source(), key, "Approved import")
        self.assertEqual(submit_import(self.actor, self.source(), key, "Repeat submission").pk, job.pk)
        self.assertEqual(OutboxEvent.objects.count(), 1)
        with self.assertRaises(ImportErrorDetail) as caught:
            submit_import(self.actor, self.source([("another", "ANOTHER")]), key, "Changed submission")
        self.assertEqual(caught.exception.status, 409)

    def test_parser_rejects_malformed_duplicate_and_oversized_content(self):
        invalid = [b"not,catalog\n", self.source([("same", "ONE"), ("same", "TWO")]), b"x" * (1024*1024+1), self.source().replace(b'""color"":""black""', b'""color"":5'), self.source().replace(b"Plain description", b"Bad\x00description"), self.source([(f"row-{n}", f"ROW-{n}") for n in range(251)])]
        for source in invalid:
            with self.assertRaises(ImportErrorDetail):
                parse_csv(source)
        self.assertFalse(CatalogImportJob.objects.exists())

    def test_role_csrf_and_source_privacy(self):
        path = "/api/v1/operations/catalog-imports/"
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(path).status_code, 403)
        self.client.force_login(self.actor)
        result = self.client.post(path, {"file": SimpleUploadedFile("catalog.csv", self.source(), content_type="text/csv"), "reason": "Approved import", "idempotency_key": str(uuid4())})
        self.assertEqual(result.status_code, 202)
        self.assertNotIn("description", result.content.decode())
        self.assertNotIn("rows", result.json()["import"])
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.actor)
        self.assertEqual(csrf.post(path, {}).status_code, 403)
        self.assertEqual(self.client.get(path + "template/")["X-Content-Type-Options"], "nosniff")

    def test_export_is_private_bounded_and_spreadsheet_safe(self):
        product = Product.objects.create(title="=dangerous formula", slug="export-product", category=self.category, description="  @formula")
        variants = Variant.objects.bulk_create([Variant(product=product, sku=f"+EXPORT-{n}") for n in range(251)])
        path = "/api/v1/operations/catalog-imports/export/"
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(path).status_code, 403)
        self.client.force_login(self.actor)
        response = self.client.get(path)
        rows = list(csv.DictReader(StringIO(response.content.decode())))
        self.assertEqual(len(rows), 250)
        self.assertEqual(rows[0]["title"], "'=dangerous formula")
        self.assertEqual(rows[0]["sku"], "'+EXPORT-0")
        self.assertEqual(rows[0]["description"], "'  @formula")
        self.assertEqual(int(response["X-Next-Variant-ID"]), variants[249].pk)
        next_page = self.client.get(path, {"after_id": response["X-Next-Variant-ID"]})
        self.assertEqual(len(list(csv.DictReader(StringIO(next_page.content.decode())))), 1)
        self.assertEqual(next_page["X-Next-Variant-ID"], "0")
        self.assertEqual(self.client.get(path, {"after_id": "invalid"}).status_code, 400)
