from django.contrib import admin
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path

from accounts import staff_views
from sellers import views as seller_views


def health(_request):
    return JsonResponse({"status": "ok"})


def ready(_request):
    try:
        connection.ensure_connection()
        cache.set("readiness_probe", "ok", 10)
        if cache.get("readiness_probe") != "ok":
            raise RuntimeError("Cache not ready")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health),
    path("ready/", ready),
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/catalog/", include("catalog.urls")),
    path("api/v1/operations/", include("operations.urls")),
    path("api/v1/admin/overview/", staff_views.overview),
    path("api/v1/admin/finance/", staff_views.finance_overview),
    path("api/v1/seller/stores/", seller_views.my_stores),
]
