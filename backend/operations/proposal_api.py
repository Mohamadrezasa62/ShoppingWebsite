from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.roles import staff_role_required
from catalog.models import Product, Variant
from sellers.models import ProductProposal, Seller
from sellers.proposal_views import proposal_data
from .api import _audit, _body, _error, _reason


@require_http_methods(["GET"])
@staff_role_required("catalog_operator", "marketplace_manager", "system_administrator")
def proposals(request):
    rows = ProductProposal.objects.filter(status="pending").order_by("pk")[:100]
    return JsonResponse({"proposals": [proposal_data(row) for row in rows]})


@require_http_methods(["POST"])
@csrf_protect
@staff_role_required("catalog_operator", "marketplace_manager", "system_administrator")
def decision(request, proposal_id):
    data = _body(request)
    reason = _reason(data) if data else None
    if not reason or data.get("status") not in ("approved", "rejected") or set(data) - {"reason", "status", "slug"}:
        return _error("invalid_proposal_decision")
    try:
        with transaction.atomic():
            seller_id = ProductProposal.objects.filter(pk=proposal_id).values_list("seller_id", flat=True).first()
            if seller_id is None:
                return _error("proposal_not_found", 404)
            seller = Seller.objects.select_for_update().get(pk=seller_id)
            row = ProductProposal.objects.select_for_update().get(pk=proposal_id)
            if row.status != "pending":
                return _error("proposal_already_reviewed", 409)
            if data["status"] == "approved":
                if seller.status != "approved" or not row.category.is_active or not isinstance(data.get("slug"), str):
                    return _error("proposal_not_approvable")
                product = Product(title=row.title, slug=data["slug"].strip(), category=row.category, description=row.description, specifications=row.specifications, status="draft")
                product.full_clean()
                product.save()
                variant = Variant(product=product, sku=row.sku, attributes=row.attributes)
                variant.full_clean()
                variant.save()
                row.product = product
            row.status, row.review_note, row.reviewed_by, row.reviewed_at = data["status"], reason, request.user, timezone.now()
            row.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "product"])
            _audit(request, "product_proposal_reviewed", "proposal", row.pk, reason, {"status": "pending"}, {"status": row.status, "product_id": row.product_id})
    except (ValidationError, IntegrityError):
        return _error("proposal_catalog_conflict", 409)
    return JsonResponse({"proposal": proposal_data(row)})
