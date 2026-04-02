"""Target: core models."""

import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Item(models.Model):
    """Target item."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(help_text="Item name")
    type = models.CharField(help_text="File type")
    size = models.IntegerField(help_text="Item size (in bytes)")
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "items"
