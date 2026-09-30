from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import SellerMembership


@require_GET
def my_stores(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    memberships = SellerMembership.objects.filter(
        user=request.user, seller__status="approved"
    ).select_related("seller")
    if not memberships.exists():
        return JsonResponse({"error": "seller_approval_required"}, status=403)
    return JsonResponse({"stores": [
        {"id": membership.seller_id, "name": membership.seller.name, "role": membership.role}
        for membership in memberships
    ]})
