from django.urls import path

from . import password_views
from . import views, export_views, closure_views
from . import email_views

urlpatterns = [
    path("email/login/", email_views.sign_in),
    path("email/register/", email_views.register),
    path("staff-password/request-code/", password_views.request_change_code),
    path("staff-password/change/", password_views.change_password),
    path("closure-requests/", closure_views.requests),
    path("closure-requests/<int:case_id>/withdraw/", closure_views.withdraw),
    path("export/", export_views.export_account),
    path("revoke-sessions/", views.revoke_sessions),
    path("csrf/", views.csrf),
    path("request-code/", views.request_phone_code),
    path("verify-code/", views.verify_phone_code),
    path("logout/", views.sign_out),
    path("me/", views.me),
]
