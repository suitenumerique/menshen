"""Source: core admin."""

from django.contrib import admin

from .models import Recording


class RecordingAdmin(admin.ModelAdmin):
    """Admin configuration for the Recording model."""


admin.site.register(Recording, RecordingAdmin)
