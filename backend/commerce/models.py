from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    updated_at = models.DateTimeField(auto_now=True)


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


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        EXPIRED = "expired", "Expired"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    idempotency_key = models.UUIDField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)
    address_snapshot = models.JSONField()
    item_total_toman = models.PositiveBigIntegerField()
    shipping_total_toman = models.PositiveBigIntegerField()
    grand_total_toman = models.PositiveBigIntegerField()
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

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Order line snapshots are immutable")
        return super().save(*args, **kwargs)
