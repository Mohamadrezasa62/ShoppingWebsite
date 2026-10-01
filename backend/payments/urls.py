from django.urls import path

from . import views

urlpatterns = [path("methods/", views.methods)]
