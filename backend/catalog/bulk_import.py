import csv
import hashlib
import json
from io import StringIO
from uuid import UUID
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_unicode_slug
from django.db import IntegrityError, transaction
from operations.events import emit
from operations.models import AuditEvent
from .models import Brand, Category, CatalogImportJob, Product, Variant

HEADERS = ("title", "slug", "category_slug", "brand_slug", "sku", "description", "attributes", "specifications")
MAX_BYTES, MAX_ROWS = 1024 * 1024, 250
ROLES = ("catalog_operator", "marketplace_manager", "system_administrator")


class ImportErrorDetail(Exception):
    def __init__(self, code, status=400):
        self.code, self.status = code, status


def authorized(user):
    return user.is_active and user.is_staff and (user.is_superuser or user.groups.filter(name__in=ROLES).exists())


def parse_csv(raw):
    if not raw or len(raw) > MAX_BYTES:
        raise ImportErrorDetail("invalid_import_size")
    try:
        source = raw.decode("utf-8-sig")
        if "\x00" in source:
            raise ImportErrorDetail("invalid_import_csv")
        reader = csv.DictReader(StringIO(source), strict=True)
        if tuple(reader.fieldnames or ()) != HEADERS:
            raise ImportErrorDetail("invalid_import_header")
        rows, seen_slugs, seen_skus = [], set(), set()
        for record in reader:
            if len(rows) >= MAX_ROWS or set(record) != set(HEADERS) or any(value is None for value in record.values()):
                raise ImportErrorDetail("invalid_import_rows")
            row = {key: value.strip() for key, value in record.items()}
            for key, minimum, maximum in [("title", 3, 240), ("slug", 1, 240), ("category_slug", 1, 160), ("brand_slug", 0, 160), ("sku", 1, 80), ("description", 0, 20000)]:
                if not minimum <= len(row[key]) <= maximum:
                    raise ImportErrorDetail("invalid_import_fields")
            for key in ("slug", "category_slug", "brand_slug"):
                if row[key]:
                    validate_unicode_slug(row[key])
            for key in ("attributes", "specifications"):
                value = json.loads(row[key] or "{}")
                if not isinstance(value, dict) or len(value) > 50 or any(not isinstance(k, str) or not isinstance(v, str) or "\x00" in k or "\x00" in v or not 1 <= len(k) <= 80 or not 1 <= len(v) <= 500 for k, v in value.items()):
                    raise ImportErrorDetail("invalid_import_attributes")
                row[key] = value
            if row["slug"] in seen_slugs or row["sku"] in seen_skus:
                raise ImportErrorDetail("duplicate_import_identifier")
            seen_slugs.add(row["slug"])
            seen_skus.add(row["sku"])
            rows.append(row)
    except (UnicodeDecodeError, csv.Error, ValidationError, json.JSONDecodeError, RecursionError):
        raise ImportErrorDetail("invalid_import_csv")
    if not rows:
        raise ImportErrorDetail("empty_import")
    return rows


def queue_event(job):
    job.last_event = emit(f"catalog-import:{job.pk}:{job.attempt}", "catalog.import", job_id=job.pk, attempt=job.attempt)
    job.save(update_fields=["last_event"])


@transaction.atomic
def submit_import(actor, raw, key, reason, mode="create"):
    try:
        key = UUID(str(key))
    except (ValueError, TypeError, AttributeError):
        raise ImportErrorDetail("invalid_idempotency_key")
    if mode not in ("create", "update"):
        raise ImportErrorDetail("invalid_import_mode")
    if mode == "update":
        from .bulk_update import parse_update_csv
        rows = parse_update_csv(raw)
    else:
        rows = parse_csv(raw)
    actor = get_user_model().objects.select_for_update(no_key=True).get(pk=actor.pk)
    if not authorized(actor):
        raise ImportErrorDetail("permission_denied", 403)
    digest = hashlib.sha256(raw).hexdigest()
    existing = CatalogImportJob.objects.filter(requested_by=actor, idempotency_key=key).first()
    if existing:
        if existing.source_digest != digest or existing.mode != mode:
            raise ImportErrorDetail("import_idempotency_conflict", 409)
        return existing
    if CatalogImportJob.objects.filter(requested_by=actor, status="queued").count() >= 5:
        raise ImportErrorDetail("import_queue_limit", 429)
    job = CatalogImportJob.objects.create(requested_by=actor, idempotency_key=key, source_digest=digest, rows=rows, row_count=len(rows), mode=mode)
    queue_event(job)
    AuditEvent.objects.create(actor=actor, action="catalog_import_submitted", target_type="catalog_import", target_id=str(job.pk), reason=reason, after={"row_count": job.row_count, "status": job.status, "mode": job.mode})
    return job


def process_import(job_id, attempt):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Imports must run inside the outbox transaction")
    reference = CatalogImportJob.objects.values_list("requested_by_id", flat=True).get(pk=job_id)
    actor = get_user_model().objects.select_for_update(no_key=True).get(pk=reference)
    job = CatalogImportJob.objects.select_for_update().get(pk=job_id)
    if job.status != "queued" or job.attempt != attempt:
        return
    index, created_ids = 0, []
    error = None
    if not authorized(actor):
        error = {"code": "authorization_revoked", "row": None}
    else:
        try:
            # Roll back the entire file on any known catalog conflict.
            with transaction.atomic():
                if job.mode == "update":
                    from .bulk_update import process_updates
                    created_ids = process_updates(job, actor)
                else:
                    for index, row in enumerate(job.rows, start=2):
                        category = Category.objects.filter(slug=row["category_slug"], is_active=True).first()
                        brand = Brand.objects.filter(slug=row["brand_slug"], is_active=True).first() if row["brand_slug"] else None
                        if category is None or (row["brand_slug"] and brand is None):
                            raise ImportErrorDetail("invalid_catalog_reference")
                        product = Product(title=row["title"], slug=row["slug"], category=category, brand=brand, description=row["description"], specifications=row["specifications"], status="draft")
                        product.full_clean()
                        product.save()
                        variant = Variant(product=product, sku=row["sku"], attributes=row["attributes"])
                        variant.full_clean()
                        variant.save()
                        created_ids.append(product.pk)
        except ImportErrorDetail as exc:
            error = {"code": exc.code, "row": getattr(exc, "row", index)}
        except (ValidationError, IntegrityError):
            error = {"code": "catalog_conflict", "row": index}
    if error:
        job.status, job.error = "failed", error
    else:
        job.status, job.product_ids, job.rows, job.error = "succeeded", created_ids, [], {}
    job.save(update_fields=["status", "product_ids", "rows", "error", "updated_at"])
    AuditEvent.objects.create(actor=actor, action="catalog_import_processed", target_type="catalog_import", target_id=str(job.pk), reason="Background catalog import processed", before={"status": "queued"}, after={"status": job.status, "error": job.error, "product_count": len(job.product_ids), "mode": job.mode})


@transaction.atomic
def retry_import(actor, job_id, reason):
    actor = get_user_model().objects.select_for_update(no_key=True).get(pk=actor.pk)
    if not authorized(actor):
        raise ImportErrorDetail("permission_denied", 403)
    job = CatalogImportJob.objects.select_for_update(of=("self",)).select_related("last_event").get(pk=job_id)
    if job.attempt >= 5 or not (job.status == "failed" or (job.status == "queued" and job.last_event and job.last_event.status == "dead")):
        raise ImportErrorDetail("import_not_retryable", 409)
    job.attempt += 1
    job.status, job.error = "queued", {}
    job.save(update_fields=["attempt", "status", "error", "updated_at"])
    queue_event(job)
    AuditEvent.objects.create(actor=actor, action="catalog_import_retried", target_type="catalog_import", target_id=str(job.pk), reason=reason, after={"attempt": job.attempt})
    return job
