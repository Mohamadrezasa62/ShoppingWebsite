from django.urls import path

from . import views

urlpatterns = [
    path("cart/", views.cart),
    path("cart/lines/<int:line_id>/", views.cart_line),
]
