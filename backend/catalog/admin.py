from django.contrib import admin

from .models import Brand, Category, CategoryFacet, Offer, Product, ProductMedia, ProductReview, Variant, WishlistItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(CategoryFacet)
class CategoryFacetAdmin(admin.ModelAdmin):
    list_display = ("category", "label", "key", "position", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("label", "key")


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
    readonly_fields = ("available_quantity", "reserved_quantity", "inventory_managed", "inventory_activated_at")

    def get_readonly_fields(self, request, obj=None):
        return (*self.readonly_fields, "seller", "variant") if obj else self.readonly_fields


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "status", "verified_purchase", "created_at")
    list_filter = ("status", "rating")
    readonly_fields = ("user", "product", "rating", "title", "body", "verified_purchase", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
    search_fields = ("variant__sku", "seller__name")
