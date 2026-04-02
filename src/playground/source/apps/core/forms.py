"""Source: core forms."""

from django import forms


class RecordingBackupForm(forms.Form):
    """Recording backup form to configured target service."""

    pk = forms.UUIDField(widget=forms.HiddenInput)
