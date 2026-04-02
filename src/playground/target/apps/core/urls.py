"""Target: core urls."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .api.views import new_items
from .api.viewsets import ItemViewSet

# API
router = DefaultRouter()
router.register(r"items", ItemViewSet, basename="item")

urlpatterns = [
    path("", views.MainView.as_view(), name="main"),
    path("external_api/", include(router.urls)),
    path("new", new_items),
]
