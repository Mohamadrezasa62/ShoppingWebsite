"""Owner-only account export. Staff notes, secrets and other users are excluded."""
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from commerce.models import Address, Order, ReturnCase
from catalog.models import ProductReview, ProductQuestion, ProductAlert, WishlistItem, ReviewMedia
from operations.models import SupportTicket, OrderDispute, NotificationPreference
from sellers.models import SellerReview
from catalog.models import BrowsingPreference, RecentProductView
from catalog.history_api import cutoff


@require_GET
def export_account(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    user = request.user
    response = JsonResponse({
        "generated_at": timezone.now().isoformat(),
        "profile": {"phone": user.phone, "first_name": user.first_name, "last_name": user.last_name},
        "addresses": list(Address.objects.filter(user=user).values("id", "full_name", "phone", "province", "city", "street", "postal_code")),
        "orders": list(Order.objects.filter(user=user).values("id", "status", "created_at", "grand_total_toman", "discount_total_toman", "tax_total_toman", "address_snapshot")),
        "returns": list(ReturnCase.objects.filter(requested_by=user).values("id", "status", "reason", "requested_amount_toman")),
        "wishlist": list(WishlistItem.objects.filter(user=user).values("product_id", "created_at")),
        "reviews": list(ProductReview.objects.filter(user=user).values("product_id", "rating", "title", "body", "status")),
        "seller_reviews": list(SellerReview.objects.filter(user=user).values("seller_id", "delivery_id", "rating", "body", "status")),
        "review_images": list(ReviewMedia.objects.filter(review__user=user).values("id", "review_id", "alt_text", "status", "created_at")),
        "questions": list(ProductQuestion.objects.filter(user=user).values("product_id", "body", "answer", "status")),
        "alerts": list(ProductAlert.objects.filter(user=user).values("product_id", "kind", "target_price_toman", "is_active")),
        "following": list(user.following.values("brand_id", "seller_id", "created_at")),
        "browsing_history_enabled": BrowsingPreference.objects.filter(user=user, enabled=True).exists(),
        "recently_viewed": list(RecentProductView.objects.filter(user=user, viewed_at__gte=cutoff()).order_by("-viewed_at", "-pk").values("product_id", "viewed_at")[:50]),
        "disputes": list(OrderDispute.objects.filter(requested_by=user).values("delivery_id", "status", "reason", "seller_response", "resolution")),
        "notification_preferences": list(NotificationPreference.objects.filter(user=user).values("marketing_in_app", "updated_at")),
        "support": [{"id": t.pk, "subject": t.subject, "status": t.status, "messages": list(t.messages.filter(is_internal=False).values("body", "created_at"))} for t in SupportTicket.objects.filter(user=user).prefetch_related("messages")],
        "scope": "Customer profile and activity; financial/legal retention and deletion policies require separate approval.",
    }, json_dumps_params={"ensure_ascii": False})
    response["Content-Disposition"] = 'attachment; filename="account-data.json"'
    response["Cache-Control"] = "no-store"
    return response
