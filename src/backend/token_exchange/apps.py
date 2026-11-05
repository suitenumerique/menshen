"""Menshen: configuration for the token_exchange application."""

from django.apps import AppConfig
from django_structlog.signals import bind_extra_request_metadata

from menshen.logging import drop_user_agent


class TxConfig(AppConfig):
    """Token exchance application configuration."""

    name = "token_exchange"

    def ready(self):
        """Connect the logging signal receivers."""
        bind_extra_request_metadata.connect(drop_user_agent, dispatch_uid="drop_user_agent")
