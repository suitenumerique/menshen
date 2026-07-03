"""Source: core views."""

import logging

import requests
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import BadRequest
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import FormView, ListView
from lasuite.oidc_login.decorators import refresh_oidc_access_token
from requests.auth import HTTPBasicAuth

from .forms import RecordingBackupForm
from .models import Recording

logger = logging.getLogger(__name__)


class MainView(ListView):
    """Source service main list view."""

    template_name = "core/main.html"
    model = Recording
    extra_context = {"recording_form": RecordingBackupForm}


class BackupView(FormView):
    """Source recording backup to target service using Token Exchange via Menshen."""

    http_method_names = ["post"]
    success_url = reverse_lazy("main")
    form_class = RecordingBackupForm

    def get_object(self):
        """Get Recording instance."""
        form = self.get_form()
        if not form.is_valid():
            raise BadRequest("Record identifier is not valid")

        pk = form.cleaned_data["pk"]
        try:
            return Recording.objects.get(id=pk)
        except Recording.DoesNotExist:
            raise Http404("Recording not found")

    @method_decorator(refresh_oidc_access_token)
    def post(self, request):
        """Process to Recording backup."""
        recording = self.get_object()

        # Generate an exchange token for backup
        token_exchange_auth = HTTPBasicAuth(
            settings.OIDC_TX_CLIENT_ID, settings.OIDC_TX_CLIENT_SECRET
        )
        token_exchange_payload = {
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token": request.session.get("oidc_access_token"),
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "audience": "playground-target",
        }
        response = requests.post(
            settings.OIDC_TX_TOKEN_ENDPOINT,
            json=token_exchange_payload,
            auth=token_exchange_auth,
        )
        response.raise_for_status()
        exchanged_token = response.json()
        logger.info(f"TX: {exchanged_token=}")

        # Use exchanged token to backup recording in the configured target service
        response = requests.post(
            "http://playground-target:8000/external_api/items/",
            data={"name": recording.meeting, "type": "video/mpeg", "size": 10240},
            headers={"Authorization": f"Bearer {exchanged_token['access_token']}"},
        )
        response.raise_for_status()
        logger.info(f"{response.json()=}")

        # Add message to the request
        messages.add_message(
            request,
            messages.SUCCESS,
            f"Recording for meeting '{recording.meeting}' successfully backed up.",
        )
        return HttpResponseRedirect(self.get_success_url())
