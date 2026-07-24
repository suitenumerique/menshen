"""Menshen: URL configuration for the token_exchange application."""

from django.urls import path

from .api import api

urlpatterns = [
    path("token/", api.urls),
]
