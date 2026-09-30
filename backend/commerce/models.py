from django.conf import settings
from django.db import models


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
