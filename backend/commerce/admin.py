from django.contrib import admin

from .models import Address, Cart, CartLine, ShippingRule


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "updated_at")
    search_fields = ("user__phone",)


@admin.register(CartLine)
class CartLineAdmin(admin.ModelAdmin):
    list_display = ("cart", "offer", "quantity")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "province", "city", "postal_code")
    search_fields = ("user__phone", "postal_code")


@admin.register(ShippingRule)
class ShippingRuleAdmin(admin.ModelAdmin):
    list_display = ("province", "fulfillment", "fee_toman", "min_days", "max_days", "is_active")
    list_filter = ("fulfillment", "is_active")
