import csv
from io import StringIO
import json
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from catalog.bulk_import import HEADERS, MAX_BYTES, ROLES, ImportErrorDetail, submit_import, retry_import
from catalog.models import CatalogImportJob, Variant
from catalog.bulk_update import UPDATE_HEADERS, content_revision
from catalog.models import Product
from .api import _body, _reason, _error


def serialize(row):
    return {"id": row.pk, "mode": row.mode, "row_count": row.row_count, "status": row.status, "attempt": row.attempt, "error": row.error, "product_ids": row.product_ids, "event_status": row.last_event.status if row.last_event else None, "created_at": row.created_at.isoformat()}


@require_http_methods(["GET", "POST"])
@csrf_protect
@staff_role_required(*ROLES)
def jobs(request):
    if request.method == "GET":
        rows = CatalogImportJob.objects.select_related("last_event").order_by("-pk")[:100]
        return JsonResponse({"imports": [serialize(row) for row in rows]})
    reason = _reason(request.POST)
    if not reason or not {"reason", "idempotency_key"}.issubset(request.POST) or not set(request.POST).issubset({"reason", "idempotency_key", "mode"}) or set(request.FILES) != {"file"}:
        return _error("invalid_import")
    upload = request.FILES["file"]
    if upload.size > MAX_BYTES:
        return _error("invalid_import_size")
    try:
        job = submit_import(request.user, upload.read(MAX_BYTES + 1), request.POST["idempotency_key"], reason, request.POST.get("mode", "create"))
    except ImportErrorDetail as exc:
        return _error(exc.code, exc.status)
    return JsonResponse({"import": serialize(job)}, status=202 if job.status == "queued" else 200)


@require_http_methods(["GET"])
@staff_role_required(*ROLES)
def template(request):
    result = StringIO()
    writer = csv.writer(result)
    writer.writerow(HEADERS)
    writer.writerow(["Example product", "example-product", "category-slug", "", "EXAMPLE-SKU", "Plain description", '{"color":"black"}', '{"screen":"large"}'])
    response = HttpResponse(result.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="catalog-import-template.csv"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_http_methods(["GET"])
@staff_role_required(*ROLES)
def export(request):
    try:
        after = int(request.GET.get("after_id", "0"))
    except ValueError:
        return _error("invalid_export_cursor")
    if not 0 <= after <= 9_000_000_000_000_000_000:
        return _error("invalid_export_cursor")
    rows = list(Variant.objects.filter(pk__gt=after).select_related("product__category", "product__brand").order_by("pk")[:251])
    result = StringIO()
    writer = csv.writer(result)
    writer.writerow(HEADERS)
    def cell(value):
        # Treat all catalog text as data in spreadsheet applications.
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
    for variant in rows[:250]:
        product = variant.product
        values = [product.title, product.slug, product.category.slug, product.brand.slug if product.brand else "", variant.sku, product.description, json.dumps(variant.attributes, ensure_ascii=False), json.dumps(product.specifications, ensure_ascii=False)]
        writer.writerow([cell(value) for value in values])
    response = HttpResponse(result.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="catalog-after-{after}.csv"'
    response["X-Next-Variant-ID"] = str(rows[249].pk) if len(rows) > 250 else "0"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required(*ROLES)
def retry(request, job_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or set(data) != {"reason"}:
        return _error("reason_required")
    get_object_or_404(CatalogImportJob, pk=job_id)
    try:
        job = retry_import(request.user, job_id, reason)
    except ImportErrorDetail as exc:
        return _error(exc.code, exc.status)
    return JsonResponse({"import": serialize(job)})


@require_http_methods(["GET"])
@staff_role_required(*ROLES)
def update_export(request):
    try:
        after = int(request.GET.get("after_id", "0"))
    except ValueError:
        return _error("invalid_export_cursor")
    if not 0 <= after <= 9_000_000_000_000_000_000:
        return _error("invalid_export_cursor")
    rows = list(Product.objects.filter(pk__gt=after).order_by("pk")[:251])
    result = StringIO()
    writer = csv.writer(result)
    writer.writerow(UPDATE_HEADERS)
    def cell(value):
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
    for product in rows[:250]:
        writer.writerow([product.pk, content_revision(product), cell(product.title), cell(product.description), json.dumps(product.specifications, ensure_ascii=False)])
    response = HttpResponse(result.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="catalog-update-after-{after}.csv"'
    response["X-Next-Product-ID"] = str(rows[249].pk) if len(rows) > 250 else "0"
    response["X-Content-Type-Options"] = "nosniff"
    return response
