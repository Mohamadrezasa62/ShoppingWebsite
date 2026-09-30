from django.contrib import admin

from .models import Brand, Category, Offer, Product, ProductMedia, Variant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    search_fields = ("name", "slug")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "brand", "status", "updated_at")
    list_filter = ("status", "category")
    search_fields = ("title", "slug")


@admin.register(ProductMedia)
class ProductMediaAdmin(admin.ModelAdmin):
    list_display = ("product", "alt_text", "position", "is_approved")
    list_filter = ("is_approved",)
    search_fields = ("product__title", "alt_text")


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "product", "is_active")
    search_fields = ("sku", "product__title")


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("variant", "seller", "price_toman", "available_quantity", "reserved_quantity", "status")
    list_filter = ("status", "fulfillment")
    search_fields = ("variant__sku", "seller__name")
