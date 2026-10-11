from django.urls import path

from . import views, reconciliation_api, investigation_api

urlpatterns = [
    path("finance/<int:attempt_id>/notes/", investigation_api.history),
    path("finance/<int:attempt_id>/notes/append/", investigation_api.append),
    path("orders/<int:order_id>/attempts/", reconciliation_api.order_attempts),
    path("finance/queue/export/", reconciliation_api.export_queue),
    path("finance/queue/", reconciliation_api.queue),
    path("finance/<int:attempt_id>/verify/", reconciliation_api.staff_verify),
    path("zarinpal/callback/<str:token>/", views.zarinpal_callback),
    path("<int:attempt_id>/verify/", views.verify_live),
    path("methods/", views.methods),
    path("initiate/", views.initiate),
    path("<int:attempt_id>/", views.detail),
    path("<int:attempt_id>/sandbox-result/", views.sandbox_result),
]
