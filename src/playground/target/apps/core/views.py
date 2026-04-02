"""Target: core views."""

import logging

from django.views.generic import ListView

from .models import Item

logger = logging.getLogger(__name__)


class MainView(ListView):
    """Target service main list view."""

    template_name = "core/main.html"
    model = Item
