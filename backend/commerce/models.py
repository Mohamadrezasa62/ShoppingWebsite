from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    updated_at = models.DateTimeField(auto_now=True)
    coupon = models.ForeignKey("Coupon", null=True, blank=True, on_delete=models.SET_NULL)


class CartLine(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="lines")
    offer = models.ForeignKey("catalog.Offer", on_delete=models.PROTECT, related_name="cart_lines")
    quantity = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "offer"], name="unique_cart_offer"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="cart_quantity_positive"),
        ]


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=13)
    province = models.CharField(max_length=120)
    city = models.CharField(max_length=120)
    street = models.CharField(max_length=500)
    postal_code = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)


class ShippingRule(models.Model):
    province = models.CharField(max_length=120)
    fulfillment = models.CharField(max_length=10, choices=(("seller", "Seller"), ("platform", "Platform")), default="seller")
    fee_toman = models.PositiveBigIntegerField()
    min_days = models.PositiveSmallIntegerField()
    max_days = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["province", "fulfillment"], name="unique_province_fulfillment_rule"),
            models.CheckConstraint(condition=models.Q(max_days__gte=models.F("min_days")), name="shipping_days_ordered"),
        ]


class ShippingMethod(models.Model):
    rule = models.ForeignKey(ShippingRule, on_delete=models.PROTECT, related_name="methods")
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=160)
    fee_toman = models.PositiveBigIntegerField()
    min_days = models.PositiveSmallIntegerField()
    max_days = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["rule", "code"], name="unique_rule_shipping_method"), models.CheckConstraint(condition=models.Q(max_days__gte=models.F("min_days")), name="shipping_method_days_ordered")]


class DeliverySlot(models.Model):
    method = models.ForeignKey(ShippingMethod, on_delete=models.PROTECT, related_name="slots")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    capacity = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="delivery_slot_time_order"), models.CheckConstraint(condition=models.Q(capacity__gt=0), name="delivery_slot_capacity_positive"), models.UniqueConstraint(fields=["method", "starts_at", "ends_at"], name="unique_method_delivery_window")]


class TaxRule(models.Model):
    category = models.OneToOneField("catalog.Category", on_delete=models.PROTECT, related_name="tax_rule")
    label = models.CharField(max_length=160)
    rate_bps = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(rate_bps__lte=10000), name="tax_rate_limit")]


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        EXPIRED = "expired", "Expired"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    idempotency_key = models.UUIDField()
    checkout_address_id = models.PositiveBigIntegerField(null=True, editable=False)
    checkout_quote_digest = models.CharField(max_length=64, blank=True, editable=False)
    checkout_shipping_methods = models.JSONField(default=dict, editable=False)
    checkout_shipping_slots = models.JSONField(default=dict, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)
    address_snapshot = models.JSONField()
    item_total_toman = models.PositiveBigIntegerField()
    shipping_total_toman = models.PositiveBigIntegerField()
    grand_total_toman = models.PositiveBigIntegerField()
    discount_total_toman = models.PositiveBigIntegerField(default=0)
    tax_total_toman = models.PositiveBigIntegerField(default=0)
    coupon_code = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "idempotency_key"], name="unique_checkout_request")]


class OrderDelivery(models.Model):
    class Status(models.TextChoices):
        AWAITING_FULFILLMENT = "awaiting_fulfillment", "Awaiting fulfillment"
        PACKING = "packing", "Packing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="deliveries")
    seller = models.ForeignKey("sellers.Seller", on_delete=models.PROTECT)
    seller_name = models.CharField(max_length=200)
    fulfillment = models.CharField(max_length=10, choices=(("seller", "Seller"), ("platform", "Platform")))
    shipping_fee_toman = models.PositiveBigIntegerField()
    shipping_method_code = models.CharField(max_length=80, default="standard")
    shipping_method_label = models.CharField(max_length=160, default="ارسال معمولی")
    shipping_slot = models.ForeignKey(DeliverySlot, null=True, blank=True, on_delete=models.PROTECT, related_name="bookings")
    delivery_window_start = models.DateTimeField(null=True, blank=True)
    delivery_window_end = models.DateTimeField(null=True, blank=True)
    min_days = models.PositiveSmallIntegerField()
    max_days = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.AWAITING_FULFILLMENT)
    tracking_code = models.CharField(max_length=120, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)


class ReturnCase(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RECEIVED = "received", "Received"
        REFUND_PENDING = "refund_pending", "Refund pending"
        REFUNDED = "refunded", "Refunded"

    delivery = models.ForeignKey(OrderDelivery, on_delete=models.PROTECT, related_name="return_cases")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    reason = models.TextField()
    requested_amount_toman = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OrderLine(models.Model):
    delivery = models.ForeignKey(OrderDelivery, on_delete=models.PROTECT, related_name="lines")
    offer = models.ForeignKey("catalog.Offer", on_delete=models.PROTECT)
    product_title = models.CharField(max_length=240)
    variant_attributes = models.JSONField()
    seller_name = models.CharField(max_length=200)
    warranty = models.CharField(max_length=200, blank=True)
    quantity = models.PositiveSmallIntegerField()
    unit_price_toman = models.PositiveBigIntegerField()
    line_total_toman = models.PositiveBigIntegerField()
    commission_bps = models.PositiveSmallIntegerField(default=0)
    discount_toman = models.PositiveBigIntegerField(default=0)
    tax_toman = models.PositiveBigIntegerField(default=0)
    tax_rate_bps = models.PositiveSmallIntegerField(default=0)
    tax_label = models.CharField(max_length=160, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(discount_toman__lte=models.F("line_total_toman")), name="order_line_discount_within_total"),
            models.CheckConstraint(condition=models.Q(commission_bps__lte=10000), name="order_line_commission_rate_limit"),
            models.CheckConstraint(condition=models.Q(tax_rate_bps__lte=10000), name="order_line_tax_rate_limit"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Order line snapshots are immutable")
        return super().save(*args, **kwargs)


class ReturnLine(models.Model):
    case = models.ForeignKey(ReturnCase, on_delete=models.PROTECT, related_name="lines")
    order_line = models.ForeignKey(OrderLine, on_delete=models.PROTECT, related_name="return_lines")
    quantity = models.PositiveSmallIntegerField()
    amount_toman = models.PositiveBigIntegerField()
    tax_amount_toman = models.PositiveBigIntegerField(default=0)
    unit_positions = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["case", "order_line"], name="unique_return_case_line"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="return_line_positive_quantity"),
        ]


class Coupon(models.Model):
    code = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=10, choices=(("fixed", "Fixed toman"), ("percent", "Percentage")))
    value = models.PositiveBigIntegerField()
    min_subtotal_toman = models.PositiveBigIntegerField(default=0)
    max_discount_toman = models.PositiveBigIntegerField(default=0)
    budget_toman = models.PositiveBigIntegerField(default=0)
    usage_limit = models.PositiveIntegerField(default=1)
    per_user_limit = models.PositiveIntegerField(default=1)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def clean(self):
        if self.kind == "percent" and not 1 <= self.value <= 100:
            raise ValidationError({"value": "Percentage must be 1 through 100"})
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "End must be after start"})
        if not self.value or not self.usage_limit or not self.per_user_limit:
            raise ValidationError("Value and usage limits must be positive")


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="coupon_redemption")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class DeliveryCancellation(models.Model):
    delivery = models.OneToOneField(OrderDelivery, on_delete=models.PROTECT, related_name="cancellation")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=2000)
    amount_toman = models.PositiveBigIntegerField()
    status = models.CharField(max_length=12, choices=(("requested", "Requested"), ("approved", "Approved"), ("rejected", "Rejected"), ("refunded", "Refunded")), default="requested")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="reviewed_cancellations")
    review_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
