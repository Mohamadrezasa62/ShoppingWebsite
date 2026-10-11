from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from accounts.roles import staff_role_required
from sellers.models import Seller
from sellers.inventory_views import inventory_payload, warehouse_data
from catalog.models import Warehouse


@require_GET
@staff_role_required("marketplace_manager", "system_administrator")
def inventory(request):
    try:
        seller_id = int(request.GET.get("seller_id", "0"))
        after = int(request.GET.get("after_id", "0"))
    except ValueError:
        return JsonResponse({"error": "invalid_cursor"}, status=400)
    if not 0 < seller_id <= 9_000_000_000_000_000_000 or not 0 <= after <= 9_000_000_000_000_000_000:
        return JsonResponse({"error": "invalid_cursor"}, status=400)
    seller = get_object_or_404(Seller, pk=seller_id)
    return JsonResponse({"seller": {"id": seller.pk, "name": seller.name, "status": seller.status}, "warehouses": [warehouse_data(row) for row in Warehouse.objects.filter(seller=seller).order_by("pk")[:20]], **inventory_payload(seller.pk, after)})
