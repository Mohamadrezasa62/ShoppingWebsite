from django.urls import path

from . import api

urlpatterns = [
    path("categories/", api.categories),
    path("brands/", api.brands),
    path("media/<int:media_id>/", api.product_media),
    path("products/", api.products),
    path("products/<slug:slug>/", api.product_detail),
]
