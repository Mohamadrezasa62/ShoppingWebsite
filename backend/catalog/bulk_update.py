"""Atomic, revision-checked editorial changes; no identity, status or stock writes."""
import csv
import hashlib
import json
from io import StringIO
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from operations.models import AuditEvent
from .models import Product

UPDATE_HEADERS = ("product_id", "revision", "title", "description", "specifications")


def content_snapshot(product):
    return {"title": product.title, "slug": product.slug,
            "description": product.description, "specifications": product.specifications,
            "category_id": product.category_id, "brand_id": product.brand_id,
            "status": product.status}


def content_revision(product):
    payload = json.dumps(content_snapshot(product), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def parse_update_csv(raw):
    from .bulk_import import ImportErrorDetail, MAX_BYTES, MAX_ROWS
    if not raw or len(raw) > MAX_BYTES:
        raise ImportErrorDetail("invalid_import_size")
    try:
        source = raw.decode("utf-8-sig")
        if "\x00" in source:
            raise ImportErrorDetail("invalid_import_csv")
        reader = csv.DictReader(StringIO(source), strict=True)
        if tuple(reader.fieldnames or ()) != UPDATE_HEADERS:
            raise ImportErrorDetail("invalid_import_header")
        rows, seen = [], set()
        for record in reader:
            if len(rows) >= MAX_ROWS or set(record) != set(UPDATE_HEADERS) or any(value is None for value in record.values()):
                raise ImportErrorDetail("invalid_import_rows")
            row = {key: value.strip() for key, value in record.items()}
            identifier = row["product_id"]
            if not identifier.isascii() or not identifier.isdecimal() or not 1 <= len(identifier) <= 18 or int(identifier) <= 0:
                raise ImportErrorDetail("invalid_product_id")
            row["product_id"] = int(identifier)
            if row["product_id"] in seen:
                raise ImportErrorDetail("duplicate_import_identifier")
            seen.add(row["product_id"])
            if len(row["revision"]) != 64 or any(c not in "0123456789abcdef" for c in row["revision"]):
                raise ImportErrorDetail("invalid_catalog_revision")
            if not 3 <= len(row["title"]) <= 240 or len(row["description"]) > 20000:
                raise ImportErrorDetail("invalid_import_fields")
            specs = json.loads(row["specifications"] or "{}")
            if not isinstance(specs, dict) or len(specs) > 50 or any(not isinstance(k, str) or not isinstance(v, str) or "\x00" in k or "\x00" in v or not 1 <= len(k) <= 80 or not 1 <= len(v) <= 500 for k, v in specs.items()):
                raise ImportErrorDetail("invalid_import_attributes")
            row["specifications"] = specs
            rows.append(row)
    except (UnicodeDecodeError, csv.Error, json.JSONDecodeError, RecursionError):
        raise ImportErrorDetail("invalid_import_csv")
    if not rows:
        raise ImportErrorDetail("empty_import")
    return rows


def process_updates(job, actor):
    from .bulk_import import ImportErrorDetail
    # One deterministic lock order regardless of CSV order; individual admin edits
    # lock these same Product rows, so the revision check cannot be overwritten.
    products = {product.pk: product for product in Product.objects.select_for_update().filter(pk__in=[row["product_id"] for row in job.rows]).order_by("pk")}
    changed = []
    for index, row in enumerate(job.rows, start=2):
        product = products.get(row["product_id"])
        if product is None or content_revision(product) != row["revision"]:
            error = ImportErrorDetail("catalog_revision_conflict")
            error.row = index
            raise error
        before = content_snapshot(product)
        for key in ("title", "description", "specifications"):
            setattr(product, key, row[key])
        try:
            product.full_clean()
            product.save(update_fields=["title", "description", "specifications", "updated_at"])
        except (ValidationError, IntegrityError):
            error = ImportErrorDetail("catalog_conflict")
            error.row = index
            raise error
        AuditEvent.objects.create(actor=actor, action="catalog_bulk_product_updated", target_type="product", target_id=str(product.pk), reason=f"Catalog content update job {job.pk}", before=before, after=content_snapshot(product))
        changed.append(product.pk)
    return changed
