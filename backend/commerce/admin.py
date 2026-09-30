from django.contrib import admin

from .models import Address, Cart, CartLine, Order, OrderDelivery, OrderLine, ShippingRule


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


class ReadOnlyOrderAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(ReadOnlyOrderAdmin):
    list_display = ("id", "user", "status", "grand_total_toman", "expires_at", "created_at")
    list_filter = ("status",)
    search_fields = ("user__phone", "id")


@admin.register(OrderDelivery)
class OrderDeliveryAdmin(ReadOnlyOrderAdmin):
    list_display = ("order", "seller_name", "fulfillment", "shipping_fee_toman")


@admin.register(OrderLine)
class OrderLineAdmin(ReadOnlyOrderAdmin):
    list_display = ("delivery", "product_title", "quantity", "line_total_toman")
