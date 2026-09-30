from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from catalog.models import Offer

from .models import Address, Cart, CartLine, Order, OrderDelivery, OrderLine, ShippingRule
from .helpers import address_data, offer_is_visible

MAX_TOTAL_TOMAN = 9_000_000_000_000_000_000


class CheckoutError(Exception):
    def __init__(self, code, status=409):
        self.code = code
        self.status = status


def parse_key(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise CheckoutError("invalid_idempotency_key", 400)


def create_order(user, address_id, idempotency_key):
    key = parse_key(idempotency_key)
    with transaction.atomic():
        existing = Order.objects.filter(user=user, idempotency_key=key).first()
        if existing:
            return existing, False
        cart = Cart.objects.select_for_update().filter(user=user).first()
        if not cart:
            raise CheckoutError("empty_cart")
        existing = Order.objects.filter(user=user, idempotency_key=key).first()
        if existing:
            return existing, False
        address = Address.objects.filter(user=user, pk=address_id).first()
        if not address:
            raise CheckoutError("address_not_found", 404)
        lines = list(CartLine.objects.select_for_update().filter(cart=cart).order_by("id"))
        if not lines:
            raise CheckoutError("empty_cart")
        offers = {offer.pk: offer for offer in Offer.objects.select_for_update().filter(
            pk__in=[line.offer_id for line in lines]
        ).order_by("pk")}
        groups = {}
        item_total = 0
        for line in lines:
            offer = offers.get(line.offer_id)
            if not offer or not offer_is_visible(offer) or offer.available_quantity - offer.reserved_quantity < line.quantity:
                raise CheckoutError("offer_unavailable")
            item_total += offer.price_toman * line.quantity
            groups[(offer.seller_id, offer.fulfillment)] = offer.seller.name
        rules = {rule.fulfillment: rule for rule in ShippingRule.objects.filter(
            province=address.province, is_active=True
        )}
        if any(fulfillment not in rules for _, fulfillment in groups):
            raise CheckoutError("shipping_unavailable")
        shipping_total = sum(rules[fulfillment].fee_toman for _, fulfillment in groups)
        if item_total + shipping_total > MAX_TOTAL_TOMAN:
            raise CheckoutError("order_total_too_large", 400)
        order = Order.objects.create(
            user=user, idempotency_key=key, address_snapshot=address_data(address),
            item_total_toman=item_total, shipping_total_toman=shipping_total,
            grand_total_toman=item_total + shipping_total,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        deliveries = {}
        for (seller_id, fulfillment), seller_name in groups.items():
            rule = rules[fulfillment]
            deliveries[(seller_id, fulfillment)] = OrderDelivery.objects.create(
                order=order, seller_id=seller_id, seller_name=seller_name,
                fulfillment=fulfillment, shipping_fee_toman=rule.fee_toman,
                min_days=rule.min_days, max_days=rule.max_days,
            )
        for line in lines:
            offer = offers[line.offer_id]
            OrderLine.objects.create(
                delivery=deliveries[(offer.seller_id, offer.fulfillment)], offer=offer,
                product_title=offer.variant.product.title,
                variant_attributes=offer.variant.attributes, seller_name=offer.seller.name,
                warranty=offer.warranty, quantity=line.quantity,
                unit_price_toman=offer.price_toman,
                line_total_toman=offer.price_toman * line.quantity,
            )
            offer.reserved_quantity += line.quantity
            offer.save(update_fields=["reserved_quantity"])
        CartLine.objects.filter(cart=cart).delete()
        return order, True


def expire_order(order_id, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status != Order.Status.PENDING_PAYMENT or order.expires_at > now:
            return False
        lines = list(OrderLine.objects.filter(delivery__order=order))
        offers = {offer.pk: offer for offer in Offer.objects.select_for_update().filter(
            pk__in=[line.offer_id for line in lines]
        ).order_by("pk")}
        for line in lines:
            offer = offers[line.offer_id]
            offer.reserved_quantity -= line.quantity
            offer.save(update_fields=["reserved_quantity"])
        order.status = Order.Status.EXPIRED
        order.save(update_fields=["status"])
        return True
