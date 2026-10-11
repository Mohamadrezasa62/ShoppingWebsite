from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from catalog.models import Category
from operations.api import _audit
from .models import ProductProposal, Seller
from .views import _auth, _membership, _data


def proposal_data(row):
    return {"id": row.pk, "seller_id": row.seller_id, "title": row.title, "category_id": row.category_id, "description": row.description, "sku": row.sku, "attributes": row.attributes, "specifications": row.specifications, "status": row.status, "review_note": row.review_note, "product_id": row.product_id}


@require_http_methods(["GET", "POST"])
@csrf_protect
def proposals(request, seller_id):
    if error := _auth(request):
        return error
    _membership(request, seller_id)
    if request.method == "POST":
        data = _data(request)
        allowed = {"title", "category_id", "description", "sku", "attributes", "specifications"}
        if not data or set(data) - allowed or type(data.get("category_id")) is not int or not isinstance(data.get("title"), str) or not isinstance(data.get("sku"), str) or not isinstance(data.get("description", ""), str) or len(data.get("description", "")) > 20000:
            return JsonResponse({"error": "invalid_proposal"}, status=400)
        for key in ("attributes", "specifications"):
            value = data.get(key, {})
            if not isinstance(value, dict) or len(value) > 50 or any(not isinstance(k, str) or not isinstance(v, str) or not 1 <= len(k) <= 80 or not 1 <= len(v) <= 500 for k, v in value.items()):
                return JsonResponse({"error": "invalid_proposal_attributes"}, status=400)
        category = get_object_or_404(Category, pk=data["category_id"], is_active=True)
        try:
            with transaction.atomic():
                seller = Seller.objects.select_for_update().get(pk=seller_id)
                if seller.status != "approved":
                    return JsonResponse({"error": "seller_not_approved"}, status=403)
                if ProductProposal.objects.filter(seller=seller, status="pending").count() >= 50:
                    return JsonResponse({"error": "proposal_limit"}, status=429)
                row = ProductProposal(seller=seller, submitted_by=request.user, category=category, title=data["title"].strip(), sku=data["sku"].strip(), description=data.get("description", "").strip(), attributes=data.get("attributes", {}), specifications=data.get("specifications", {}))
                row.full_clean()
                row.save()
                _audit(request, "product_proposed", "proposal", row.pk, "Seller submitted product proposal", {}, {"seller_id": seller.pk, "status": row.status})
        except ValidationError:
            return JsonResponse({"error": "invalid_proposal"}, status=400)
        return JsonResponse({"proposal": proposal_data(row)}, status=201)
    rows = ProductProposal.objects.filter(seller_id=seller_id).order_by("-pk")[:100]
    return JsonResponse({"proposals": [proposal_data(row) for row in rows]})
