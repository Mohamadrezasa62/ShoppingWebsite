from django.urls import path

from . import merchandising
from . import api, alert_api, follow_api
from . import trust_api, question_api
from . import comparison_api
from . import review_media_api
from . import history_api

urlpatterns = [
    path("history/", history_api.history),
    path("history/views/", history_api.record),
    path("my-reviews/", review_media_api.mine),
    path("my-reviews/<int:review_id>/images/", review_media_api.upload),
    path("review-images/<int:image_id>/preview/", review_media_api.preview),
    path("review-images/<int:image_id>/withdraw/", review_media_api.withdraw),
    path("review-images/<int:image_id>/", review_media_api.public),
    path("compare/", comparison_api.compare),
    path("following/", follow_api.following),
    path("following/<int:follow_id>/", follow_api.unfollow),
    path("feed/", follow_api.feed),
    path("collections/", merchandising.collections),
    path("collections/<slug:slug>/", merchandising.collection),
    path("products/<int:product_id>/related/", merchandising.related),
    path("alerts/", alert_api.alerts),
    path("alerts/<int:alert_id>/", alert_api.delete_alert),
    path("questions/<int:product_id>/", question_api.questions),
    path("sitemap/", api.sitemap),
    path("wishlist/", trust_api.wishlist),
    path("wishlist/<int:product_id>/", trust_api.remove_wishlist),
    path("reviews/<int:product_id>/", trust_api.reviews),
    path("categories/", api.categories),
    path("brands/", api.brands),
    path("facets/", api.facets),
    path("suggestions/", api.suggestions),
    path("media/<int:media_id>/", api.product_media),
    path("products/", api.products),
    path("products/<slug:slug>/", api.product_detail),
]
