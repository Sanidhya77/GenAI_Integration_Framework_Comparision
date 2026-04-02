"""Root URL configuration for Django experiment app."""

from django.urls import path, include

urlpatterns = [
    path("", include("api.urls")),
]