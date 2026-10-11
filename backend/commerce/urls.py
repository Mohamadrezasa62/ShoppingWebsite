from django.urls import path

from . import views
from . import return_views
from . import promotion_views
from . import invoices

from . import cancellation_views

urlpatterns = [
    path("cancellations/", cancellation_views.cancellations),
    path("deliveries/<int:delivery_id>/cancellation/", cancellation_views.request_cancel),
    path("orders/<int:order_id>/invoice/", invoices.invoice),
    path("cart/coupon/", promotion_views.cart_coupon),
    path("returns/", return_views.returns),
    path("deliveries/<int:delivery_id>/returns/", return_views.request_return),
    path("cart/", views.cart),
    path("cart/lines/<int:line_id>/", views.cart_line),
    path("addresses/", views.addresses),
    path("addresses/<int:address_id>/", views.delete_address),
    path("quote/", views.quote),
    path("checkout/", views.checkout),
    path("orders/", views.orders),
    path("orders/<int:order_id>/", views.order_detail),
    path("orders/<int:order_id>/cancel/", views.cancel_order),
]
