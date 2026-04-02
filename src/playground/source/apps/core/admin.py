"""Source: core admin."""

from django.contrib import admin

from .models import Recording


class RecordingAdmin(admin.ModelAdmin):
    pass


admin.site.register(Recording, RecordingAdmin)
