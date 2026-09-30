from django.urls import path

from . import views

urlpatterns = [
    path("stores/", views.my_stores),
    path("applications/", views.apply),
    path("catalog-variants/", views.catalog_variants),
    path("stores/<int:seller_id>/offers/", views.offers),
    path("stores/<int:seller_id>/profile/", views.update_profile),
    path("stores/<int:seller_id>/offers/<int:offer_id>/", views.update_offer),
]
