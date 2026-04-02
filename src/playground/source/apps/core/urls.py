"""Source: core urls."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.MainView.as_view(), name="main"),
    path("backup", views.BackupView.as_view(), name="backup"),
]
