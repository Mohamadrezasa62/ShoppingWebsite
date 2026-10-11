from django.urls import path
from operations import dispute_api

from . import views, proposal_views
from . import order_views
from . import finance_views
from . import import_views
from . import review_api
from . import inventory_views
from . import inventory_csv

urlpatterns = [
    path("stores/<int:seller_id>/inventory-csv/", inventory_csv.inventory_csv),
    path("stores/<int:seller_id>/warehouses/", inventory_views.warehouses),
    path("stores/<int:seller_id>/warehouses/<int:warehouse_id>/", inventory_views.warehouse),
    path("stores/<int:seller_id>/inventory/", inventory_views.inventory),
    path("stores/<int:seller_id>/inventory/<int:offer_id>/activate/", inventory_views.activate),
    path("stores/<int:seller_id>/inventory/<int:offer_id>/adjust/", inventory_views.adjust),
    path("stores/<int:seller_id>/inventory/<int:offer_id>/transfer/", inventory_views.transfer),
    path("stores/<int:seller_id>/inventory/<int:offer_id>/history/", inventory_views.history),
    path("reviews/", review_api.mine),
    path("public/<int:seller_id>/reviews/", review_api.public),
    path("stores/<int:seller_id>/disputes/", dispute_api.seller_cases),
    path("stores/<int:seller_id>/proposals/", proposal_views.proposals),
    path("stores/<int:seller_id>/performance/", finance_views.performance),
    path("stores/<int:seller_id>/offers-csv/", import_views.offers_csv),
    path("stores/<int:seller_id>/finance/", finance_views.finance),
    path("stores/<int:seller_id>/deliveries/", order_views.deliveries),
    path("stores/<int:seller_id>/deliveries/<int:delivery_id>/transition/", order_views.advance_delivery),
    path("stores/", views.my_stores),
    path("applications/", views.apply),
    path("catalog-variants/", views.catalog_variants),
    path("stores/<int:seller_id>/offers/", views.offers),
    path("stores/<int:seller_id>/profile/", views.update_profile),
    path("stores/<int:seller_id>/offers/<int:offer_id>/", views.update_offer),
]
