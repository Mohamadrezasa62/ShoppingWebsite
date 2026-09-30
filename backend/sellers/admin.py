from django.contrib import admin

from .models import Seller, SellerMembership


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ("name", "legal_name", "business_identifier", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "legal_name", "business_identifier")


@admin.register(SellerMembership)
class SellerMembershipAdmin(admin.ModelAdmin):
    list_display = ("seller", "user", "role", "created_at")
    list_filter = ("role",)
