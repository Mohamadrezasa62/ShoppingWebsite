from django.urls import path

from . import api

urlpatterns = [
    path("categories/", api.categories),
    path("products/", api.products),
    path("products/<slug:slug>/", api.product_detail),
]
