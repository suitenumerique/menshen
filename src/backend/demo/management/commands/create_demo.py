"""Menshen: create_demo management command."""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.tx import models as tx_models

logger = logging.getLogger(__name__)


def create_demo(stdout):
    """
    Create a database with demo data for developers to work in a realistic environment.
    The code is engineered to create a huge number of objects fast.
    """
    # Create token exchange base configuration
    stdout.write("Creating token exchange base configuration")

    menshen_service_provider, _ = tx_models.ServiceProvider.objects.get_or_create(
        name="Menshen",  # yeah that's me!
        audience_id="menshen",
    )
    docs_service_provider, _ = tx_models.ServiceProvider.objects.get_or_create(
        name="Docs",
        audience_id="docs",
    )

    tx_models.ServiceProviderCredentials.objects.get_or_create(
        service_provider=menshen_service_provider,
        client_id="client_id",
        client_secret="client_secret",  # noqa: S106
    )

    menshen_to_menshen_rule, _ = tx_models.TokenExchangeRule.objects.get_or_create(
        source_service=menshen_service_provider,
        target_service=menshen_service_provider,
    )
    tx_models.ScopeGrant.objects.get_or_create(
        rule=menshen_to_menshen_rule,
        source_scope="openid",
        granted_scope="openid",
    )
    tx_models.ScopeGrant.objects.get_or_create(
        rule=menshen_to_menshen_rule,
        source_scope="openid",
        granted_scope="docs:read",
    )

    menshen_to_docs_rule, _ = tx_models.TokenExchangeRule.objects.get_or_create(
        source_service=menshen_service_provider,
        target_service=docs_service_provider,
    )
    tx_models.ScopeGrant.objects.get_or_create(
        rule=menshen_to_docs_rule,
        source_scope="openid",
        granted_scope="openid",
    )

    simple_action, _ = tx_models.ActionScope.objects.get_or_create(
        name="action:create-docs-for-groups",
    )
    tx_models.ActionScopeGrant.objects.get_or_create(
        action=simple_action,
        target_service=docs_service_provider,
        granted_scope="docs:write",
    )
    tx_models.ActionScopeGrant.objects.get_or_create(
        action=simple_action,
        target_service=menshen_service_provider,
        granted_scope="teams:read",
    )
    tx_models.TokenExchangeActionPermission.objects.get_or_create(
        rule=menshen_to_docs_rule,
        action=simple_action,
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
