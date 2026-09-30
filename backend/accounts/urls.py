from django.urls import path

from . import views

urlpatterns = [
    path("csrf/", views.csrf),
    path("request-code/", views.request_phone_code),
    path("verify-code/", views.verify_phone_code),
    path("logout/", views.sign_out),
    path("me/", views.me),
]
