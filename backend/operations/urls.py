from django.urls import path

from . import api

urlpatterns = [
    path("summary/", api.summary),
    path("sellers/", api.sellers),
    path("sellers/<int:seller_id>/decision/", api.decide_seller),
    path("categories/", api.categories),
    path("categories/<int:category_id>/", api.update_category),
    path("staff/", api.staff),
    path("staff/<int:user_id>/roles/", api.set_staff_roles),
    path("audit/", api.audit_log),
]
