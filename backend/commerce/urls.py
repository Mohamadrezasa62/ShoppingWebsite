from django.urls import path

from . import views

urlpatterns = [
    path("cart/", views.cart),
    path("cart/lines/<int:line_id>/", views.cart_line),
    path("addresses/", views.addresses),
    path("addresses/<int:address_id>/", views.delete_address),
    path("quote/", views.quote),
    path("checkout/", views.checkout),
    path("orders/", views.orders),
    path("orders/<int:order_id>/", views.order_detail),
]
