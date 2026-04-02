"""
URL configuration for target project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from lasuite.oidc_login.urls import urlpatterns as oidc_urls

from apps.core.urls import urlpatterns as core_urls

urlpatterns = (
    [
        path("admin/", admin.site.urls),
    ]
    + oidc_urls
    + core_urls
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
)
