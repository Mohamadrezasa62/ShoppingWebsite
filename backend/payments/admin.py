from django.contrib import admin

from .models import LedgerEntry, PaymentAttempt


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "status", "amount_toman", "provider_reference", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("provider_reference", "order__id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "attempt", "kind", "amount_toman", "event_key", "created_at")
    list_filter = ("kind",)
    search_fields = ("event_key", "order__id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
