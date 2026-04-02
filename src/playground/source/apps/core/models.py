"""Source: core models."""

import uuid

from django.db import models


class Recording(models.Model):
    """Source recordings."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.CharField(help_text="Meeting name")
    meeting_id = models.UUIDField(help_text="Meeting identifier")
    duration = models.IntegerField(help_text="Recording duration (in seconds)")
    held_at = models.DateTimeField(help_text="Meeting date & time")
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ["-held_at"]
        verbose_name_plural = "recordings"
