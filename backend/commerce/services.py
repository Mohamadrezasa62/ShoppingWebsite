from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone

from catalog.models import Offer, Product
from catalog.inventory import InventoryError, reserve_line, finish_line

from .models import Address, Cart, CartLine, Coupon, CouponRedemption, Order, OrderDelivery, OrderLine, ShippingRule
from operations.events import emit
from .taxes import calculate_taxes
from .promotions import allocate_discount, coupon_discount
from .helpers import address_data, offer_is_visible
from .quotes import QuoteError, read_quote, quote_digest
from .shipping import validate_choices, resolve_choices, resolve_slots, group_key, ShippingChoiceError

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


def create_order(user, address_id, idempotency_key, quote_token=None, shipping_methods=None, shipping_slots=None):
    key = parse_key(idempotency_key)
    try:
        selections = validate_choices(shipping_methods)
        slots = validate_choices(shipping_slots)
    except ShippingChoiceError as error:
        raise CheckoutError(error.code, 400)
    if (selections or slots) and quote_token is None:
        raise CheckoutError("quote_required", 400)
    with transaction.atomic():
        # Serialize account changes/checkouts while allowing audit FK key-share
        # locks held by a staff buyer editing a shipping rule concurrently.
        account = get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
        if not account.is_active:
            raise CheckoutError("account_unavailable", 403)
        existing = Order.objects.filter(user=user, idempotency_key=key).first()
        if existing:
            if existing.checkout_shipping_methods != selections or existing.checkout_shipping_slots != slots:
                raise CheckoutError("idempotency_conflict")
            if existing.checkout_address_id is not None and existing.checkout_address_id != address_id:
                raise CheckoutError("idempotency_conflict")
            _check_quote_replay(existing, user, address_id, quote_token)
            return existing, False
        cart = Cart.objects.select_for_update().filter(user=user).first()
        if not cart:
            raise CheckoutError("empty_cart")
        existing = Order.objects.filter(user=user, idempotency_key=key).first()
        if existing:
            if existing.checkout_shipping_methods != selections or existing.checkout_shipping_slots != slots:
                raise CheckoutError("idempotency_conflict")
            if existing.checkout_address_id is not None and existing.checkout_address_id != address_id:
                raise CheckoutError("idempotency_conflict")
            _check_quote_replay(existing, user, address_id, quote_token)
            return existing, False
        address = Address.objects.select_for_update().filter(user=user, pk=address_id).first()
        if not address:
            raise CheckoutError("address_not_found", 404)
        lines = list(CartLine.objects.select_for_update().filter(cart=cart).order_by("id"))
        if not lines:
            raise CheckoutError("empty_cart")
        offers = {offer.pk: offer for offer in Offer.objects.select_for_update().filter(
            pk__in=[line.offer_id for line in lines]
        ).order_by("pk")}
        # Freeze product/category identity before pricing and tax snapshots.
        # NO KEY UPDATE permits unrelated variant FK inserts while blocking edits.
        products = {product.pk: product for product in Product.objects.select_for_update(no_key=True).filter(
            pk__in={offer.variant.product_id for offer in offers.values()}
        ).order_by("pk")}
        for offer in offers.values():
            offer.variant.product = products[offer.variant.product_id]
        groups = {}
        item_total = 0
        for line in lines:
            offer = offers.get(line.offer_id)
            if not offer or not offer_is_visible(offer) or offer.available_quantity - offer.reserved_quantity < line.quantity:
                raise CheckoutError("offer_unavailable")
            item_total += offer.price_toman * line.quantity
            groups[(offer.seller_id, offer.fulfillment)] = offer.seller.name
        rules = {rule.fulfillment: rule for rule in ShippingRule.objects.select_for_update().filter(
            province=address.province, is_active=True
        ).order_by("pk")}
        if any(fulfillment not in rules for _, fulfillment in groups):
            raise CheckoutError("shipping_unavailable")
        try:
            selected, _ = resolve_choices(groups, rules, selections, lock=True)
            windows, _ = resolve_slots(selected, slots, lock=True)
        except ShippingChoiceError as error:
            raise CheckoutError(error.code)
        shipping_total = sum(item["fee_toman"] for item in selected.values())
        coupon = Coupon.objects.select_for_update().get(pk=cart.coupon_id) if cart.coupon_id else None
        try:
            discount = coupon_discount(coupon, item_total, user)
        except ValueError as error:
            raise CheckoutError(str(error))
        taxes = calculate_taxes(lines, offers, discount, lock=True)
        if any(not offer_is_visible(offer) for offer in offers.values()):
            raise CheckoutError("offer_unavailable")
        tax_total = sum(row["amount_toman"] for row in taxes)
        approved_digest = ""
        if quote_token is not None:
            try:
                approved_digest = read_quote(quote_token, user.pk, address_id)
            except QuoteError as error:
                raise CheckoutError(error.code)
            if approved_digest != quote_digest(address_data(address), lines, offers, rules, coupon, discount, selected, windows, taxes):
                raise CheckoutError("quote_changed")
        discounts = allocate_discount([offers[line.offer_id].price_toman * line.quantity for line in lines], discount)
        if item_total + shipping_total + tax_total > MAX_TOTAL_TOMAN:
            raise CheckoutError("order_total_too_large", 400)
        order = Order.objects.create(
            user=user, idempotency_key=key, address_snapshot=address_data(address),
            checkout_address_id=address_id,
            checkout_quote_digest=approved_digest,
            checkout_shipping_methods=selections,
            checkout_shipping_slots=slots,
            item_total_toman=item_total, shipping_total_toman=shipping_total,
            grand_total_toman=item_total + shipping_total - discount + tax_total,
            tax_total_toman=tax_total,
            discount_total_toman=discount, coupon_code=coupon.code if coupon else "",
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        deliveries = {}
        for (seller_id, fulfillment), seller_name in groups.items():
            method = selected[group_key(seller_id, fulfillment)]
            window = windows[group_key(seller_id, fulfillment)]
            deliveries[(seller_id, fulfillment)] = OrderDelivery.objects.create(
                order=order, seller_id=seller_id, seller_name=seller_name,
                fulfillment=fulfillment, shipping_fee_toman=method["fee_toman"],
                min_days=method["min_days"], max_days=method["max_days"],
                shipping_method_code=method["code"], shipping_method_label=method["label"],
                shipping_slot_id=window["id"] if window else None,
                delivery_window_start=window["starts_at"] if window else None,
                delivery_window_end=window["ends_at"] if window else None,
            )
        for line, line_discount, tax in zip(lines, discounts, taxes):
            offer = offers[line.offer_id]
            order_line = OrderLine.objects.create(
                delivery=deliveries[(offer.seller_id, offer.fulfillment)], offer=offer,
                product_title=offer.variant.product.title,
                variant_attributes=offer.variant.attributes, seller_name=offer.seller.name,
                warranty=offer.warranty, quantity=line.quantity,
                unit_price_toman=offer.price_toman,
                line_total_toman=offer.price_toman * line.quantity,
                commission_bps=offer.seller.commission_bps,
                discount_toman=line_discount,
                tax_toman=tax["amount_toman"], tax_rate_bps=tax["rate_bps"], tax_label=tax["label"],
            )
            try:
                reserve_line(offer, order_line)
            except InventoryError as error:
                raise CheckoutError(error.code)
        CartLine.objects.filter(cart=cart).delete()
        if coupon:
            CouponRedemption.objects.create(coupon=coupon, order=order, user=user)
            cart.coupon = None
            cart.save(update_fields=["coupon", "updated_at"])
        emit(f"order:{order.pk}:created", "order.created", order_id=order.pk)
        return order, True


def _check_quote_replay(order, user, address_id, token):
    if not order.checkout_quote_digest and token is None:
        return
    try:
        digest = read_quote(token, user.pk, address_id, replay=True)
    except QuoteError as error:
        raise CheckoutError(error.code)
    if digest != order.checkout_quote_digest:
        raise CheckoutError("idempotency_conflict")


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
            try:
                finish_line(offer, line, consume=False)
            except InventoryError as error:
                raise CheckoutError(error.code)
        order.status = Order.Status.EXPIRED
        order.save(update_fields=["status"])
        emit(f"order:{order.pk}:expired", "order.expired", order_id=order.pk)
        return True


def cancel_unpaid_order(order_id, user):
    """Lock in the same order as capture/expiration and release exactly once."""
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
        if order is None:
            raise CheckoutError("order_not_found", 404)
        if order.status == Order.Status.CANCELLED:
            return order
        if order.status != Order.Status.PENDING_PAYMENT:
            raise CheckoutError("order_not_cancellable")
        lines = list(OrderLine.objects.filter(delivery__order=order))
        offers = {offer.pk: offer for offer in Offer.objects.select_for_update().filter(
            pk__in=[line.offer_id for line in lines]
        ).order_by("pk")}
        for line in lines:
            offer = offers[line.offer_id]
            try:
                finish_line(offer, line, consume=False)
            except InventoryError as error:
                raise CheckoutError(error.code)
        from .models import OrderDelivery
        order.deliveries.update(status=OrderDelivery.Status.CANCELLED)
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        emit(f"order:{order.pk}:cancelled", "order.cancelled", order_id=order.pk)
        return order
