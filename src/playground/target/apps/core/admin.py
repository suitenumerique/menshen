"""Target: core admin."""

from django.contrib import admin

from .models import Item


class ItemAdmin(admin.ModelAdmin):
    """Admin configuration for the Item model."""


admin.site.register(Item, ItemAdmin)
