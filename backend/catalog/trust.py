from commerce.models import Order, OrderDelivery, OrderLine

from .models import ProductReview, WishlistItem


class ReviewError(Exception):
    pass


def add_wishlist_item(user, product):
    return WishlistItem.objects.get_or_create(user=user, product=product)[0]


def submit_review(user, product, rating, title, body):
    if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5:
        raise ReviewError("Rating must be from 1 to 5")
    if not title.strip() or not body.strip():
        raise ReviewError("Review title and body are required")
    purchased = OrderLine.objects.filter(
        offer__variant__product=product,
        delivery__order__user=user,
        delivery__order__status=Order.Status.PAID,
        delivery__status=OrderDelivery.Status.DELIVERED,
    ).exists()
    if not purchased:
        raise ReviewError("A delivered purchase is required")
    if ProductReview.objects.filter(user=user, product=product).exists():
        raise ReviewError("Product has already been reviewed")
    return ProductReview.objects.create(
        user=user, product=product, rating=rating,
        title=title.strip(), body=body.strip(),
    )
