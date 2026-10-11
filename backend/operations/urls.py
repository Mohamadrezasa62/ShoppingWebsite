from django.urls import path

from . import api
from . import catalog_api
from . import order_api
from . import trust_api, question_api
from . import return_api
from . import finance_api
from . import support_api, content_api
from . import promotion_api
from . import configuration_api
from . import collection_api
from . import proposal_api, media_api
from . import report_api, event_api

from . import cancellation_api
from . import dispute_api
from . import campaign_api
from . import import_api
from accounts import closure_views
from sellers import review_api as seller_review_api
from catalog import review_media_api
from . import risk_api
from . import inventory_api
from . import shipping_method_api
from . import tax_api
from . import delivery_slot_api

urlpatterns = [
    path("categories/<int:category_id>/tax/", tax_api.rule),
    path("inventory/", inventory_api.inventory),
    path("risk-cases/", risk_api.queue),
    path("risk-cases/create/", risk_api.create),
    path("risk-cases/<int:case_id>/decision/", risk_api.decision),
    path("support-assignees/", support_api.assignees),
    path("tickets/<int:ticket_id>/route/", support_api.route),
    path("review-images/", review_media_api.queue),
    path("review-images/<int:image_id>/decision/", review_media_api.decision),
    path("seller-reviews/", seller_review_api.queue),
    path("seller-reviews/<int:review_id>/decision/", seller_review_api.decision),
    path("catalog-imports/", import_api.jobs),
    path("catalog-imports/template/", import_api.template),
    path("catalog-imports/export/", import_api.export),
    path("catalog-imports/update-export/", import_api.update_export),
    path("catalog-imports/<int:job_id>/retry/", import_api.retry),
    path("notification-preferences/", campaign_api.preferences),
    path("campaigns/", campaign_api.campaigns),
    path("campaigns/<int:campaign_id>/action/", campaign_api.action),
    path("my-disputes/", dispute_api.mine),
    path("disputes/", dispute_api.queue),
    path("disputes/<int:case_id>/decision/", dispute_api.decision),
    path("account-closures/", closure_views.staff_requests),
    path("account-closures/<int:case_id>/decision/", closure_views.decision),
    path("cancellations/", cancellation_api.cancellations),
    path("cancellations/<int:case_id>/decision/", cancellation_api.decision),
    path("cancellations/<int:case_id>/sandbox-refund/", cancellation_api.refund),
    path("brands/", configuration_api.brands),
    path("brands/<int:brand_id>/", configuration_api.brand),
    path("categories/<int:category_id>/facets/", configuration_api.facets),
    path("facets/<int:facet_id>/", configuration_api.facet),
    path("shipping-rules/", configuration_api.shipping_rules),
    path("shipping-rules/<int:rule_id>/methods/", shipping_method_api.methods),
    path("shipping-methods/<int:method_id>/", shipping_method_api.update),
    path("shipping-methods/<int:method_id>/slots/", delivery_slot_api.slots),
    path("delivery-slots/<int:slot_id>/", delivery_slot_api.update),
    path("shipping-rules/<int:rule_id>/", configuration_api.shipping_rule),
    path("collections/", collection_api.collections),
    path("collections/<int:collection_id>/", collection_api.update),
    path("products/<int:product_id>/media/", media_api.media),
    path("media/<int:media_id>/preview/", media_api.preview),
    path("media/<int:media_id>/", media_api.decision),
    path("proposals/", proposal_api.proposals),
    path("proposals/<int:proposal_id>/decision/", proposal_api.decision),
    path("reports/sellers/<int:seller_id>/", report_api.seller_performance),
    path("events/", event_api.events),
    path("events/<int:event_id>/replay/", event_api.replay),
    path("questions/", question_api.questions),
    path("questions/<int:question_id>/decision/", question_api.decision),
    path("reports/sales/", report_api.sales),
    path("coupons/", promotion_api.coupons),
    path("coupons/<int:coupon_id>/status/", promotion_api.coupon_status),
    path("my-tickets/<int:ticket_id>/", support_api.conversation),
    path("tickets/<int:ticket_id>/", support_api.staff_conversation),
    path("my-tickets/", support_api.tickets),
    path("my-tickets/<int:ticket_id>/reply/", support_api.reply),
    path("tickets/", support_api.staff_tickets),
    path("tickets/<int:ticket_id>/reply/", support_api.staff_reply),
    path("notifications/", support_api.notifications),
    path("notifications/<int:notification_id>/read/", support_api.read_notification),
    path("content/", content_api.pages),
    path("content/<slug:slug>/", content_api.page),
    path("pages/", content_api.staff_pages),
    path("pages/<int:page_id>/", content_api.update_page),
    path("pages/<int:page_id>/revisions/", content_api.revisions),
    path("pages/<int:page_id>/restore/", content_api.restore),
    path("transactions/", finance_api.transactions),
    path("sellers/<int:seller_id>/commission/", finance_api.commission),
    path("settlements/", finance_api.settlements),
    path("settlements/<int:settlement_id>/action/", finance_api.settlement_action),
    path("returns/", return_api.returns),
    path("returns/<int:case_id>/decision/", return_api.decision),
    path("returns/<int:case_id>/sandbox-refund/", return_api.sandbox_refund),
    path("reviews/", trust_api.reviews),
    path("reviews/<int:review_id>/decision/", trust_api.moderate_review),
    path("orders/", order_api.orders),
    path("orders/<int:order_id>/", order_api.order_detail),
    path("deliveries/<int:delivery_id>/transition/", order_api.advance_delivery),
    path("products/", catalog_api.products),
    path("products/<int:product_id>/", catalog_api.update_product),
    path("products/<int:product_id>/variants/", catalog_api.create_variant),
    path("summary/", api.summary),
    path("sellers/", api.sellers),
    path("sellers/<int:seller_id>/decision/", api.decide_seller),
    path("categories/", api.categories),
    path("categories/<int:category_id>/", api.update_category),
    path("staff/", api.staff),
    path("staff/<int:user_id>/roles/", api.set_staff_roles),
    path("audit/", api.audit_log),
]
