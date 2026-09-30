from django.contrib import admin

from .models import Seller, SellerMembership


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name",)


@admin.register(SellerMembership)
class SellerMembershipAdmin(admin.ModelAdmin):
    list_display = ("seller", "user", "role", "created_at")
    list_filter = ("role",)
