"""Menshen: create_demo management command."""

import logging
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from token_exchange import models as tx_models

logger = logging.getLogger(__name__)


def create_demo(stdout):
    """Create a database with demo data for developers to work in a realistic environment."""
    # Create token exchange base configuration
    stdout.write("Creating token exchange base configuration")

    # Service providers
    source_service, _ = tx_models.ServiceProvider.objects.get_or_create(
        name="playground:source",
        audience_id="playground-source",
    )
    target_service, _ = tx_models.ServiceProvider.objects.get_or_create(
        name="playground:target",
        audience_id="playground-target",
    )

    # Credentials
    tx_models.ServiceProviderCredentials.objects.get_or_create(
        service_provider=source_service,
        client_id=os.environ.get("TOKEN_EXCHANGE_DEMO_SOURCE_CLIENT_ID"),
        client_secret=os.environ.get("TOKEN_EXCHANGE_DEMO_SOURCE_CLIENT_SECRET"),
    )
    tx_models.ServiceProviderCredentials.objects.get_or_create(
        service_provider=target_service,
        client_id=os.environ.get("TOKEN_EXCHANGE_DEMO_TARGET_CLIENT_ID"),
        client_secret=os.environ.get("TOKEN_EXCHANGE_DEMO_TARGET_CLIENT_SECRET"),
    )

    # Rules
    source_to_target_rule, _ = tx_models.TokenExchangeRule.objects.get_or_create(
        source_service=source_service,
        target_service=target_service,
    )

    # Scopes
    tx_models.ScopeGrant.objects.get_or_create(
        rule=source_to_target_rule,
        source_scope="openid",
        granted_scope="openid",
    )
    tx_models.ScopeGrant.objects.get_or_create(
        rule=source_to_target_rule,
        source_scope="openid",
        granted_scope="target:read",
    )
    tx_models.ScopeGrant.objects.get_or_create(
        rule=source_to_target_rule,
        source_scope="target:write",
        granted_scope="target:write",
    )

    # Actions
    target_write_action, _ = tx_models.ActionScope.objects.get_or_create(
        name="action:write-to-target",
    )
    tx_models.ActionScopeGrant.objects.get_or_create(
        action=target_write_action,
        target_service=target_service,
        granted_scope="target:write",
    )
    target_read_action, _ = tx_models.ActionScope.objects.get_or_create(
        name="action:read-target",
    )
    tx_models.ActionScopeGrant.objects.get_or_create(
        action=target_read_action,
        target_service=target_service,
        granted_scope="target:read",
    )
    tx_models.TokenExchangeActionPermission.objects.get_or_create(
        rule=source_to_target_rule,
        action=target_write_action,
    )


class Command(BaseCommand):
    """A management command to create a demo database."""

    help = __doc__

    def add_arguments(self, parser):
        """Add argument to require forcing execution when not in debug mode."""
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            default=False,
            help="Force command execution despite DEBUG is set to False",
        )

    def handle(self, *args, **options):
        """Handle the management command."""
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "This command is not meant to be used in production environment "
                "except you know what you are doing, if so use --force parameter"
            )

        create_demo(self.stdout)
