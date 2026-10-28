"""Menshen: create_demo management command."""

import logging
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from token_exchange import models as tx_models

logger = logging.getLogger(__name__)

# La Suite services: audience ids match the Keycloak client ids of the realm
# (docker/auth/realm.json), credentials are "<audience_id>"/"<audience_id>-secret"
LASUITE_SERVICES = ("find", "docs", "drive")


# Find indexes documents from other services and searches them: each source
# service may search and delete its own documents, as `find:<service>:<action>`.
# Each scope is issued using an action scope
LASUITE_FIND_ACTIONS = {
    "docs": {
        "action:search-find-docs": "find:docs:search",
        "action:delete-find-docs": "find:docs:delete",
    },
    "drive": {
        "action:search-find-drive": "find:drive:search",
        "action:delete-find-drive": "find:drive:delete",
    },
}


def create_lasuite_demo(stdout):
    """Create La Suite services and the token exchange rules targeting Find."""
    stdout.write("Creating La Suite services configuration")

    services = {}
    for audience_id in LASUITE_SERVICES:
        services[audience_id], _ = tx_models.ServiceProvider.objects.get_or_create(
            audience_id=audience_id,
            defaults={"name": f"lasuite:{audience_id}"},
        )
        credentials, _ = tx_models.ServiceProviderCredentials.objects.get_or_create(
            service_provider=services[audience_id],
            client_id=audience_id,
        )
        credentials.set_client_secret(f"{audience_id}-secret", save=True)

    for source, actions in LASUITE_FIND_ACTIONS.items():
        rule, _ = tx_models.TokenExchangeRule.objects.get_or_create(
            source_service=services[source],
            target_service=services["find"],
        )
        for name, granted_scope in actions.items():
            action, _ = tx_models.ActionScope.objects.get_or_create(name=name)
            tx_models.ActionScopeGrant.objects.get_or_create(
                action=action,
                target_service=services["find"],
                granted_scope=granted_scope,
            )
            tx_models.TokenExchangeActionPermission.objects.get_or_create(
                rule=rule,
                action=action,
            )


def create_demo(stdout):
    """Create a database with demo data for developers to work in a realistic environment."""
    # Create token exchange base configuration
    stdout.write("Creating token exchange base configuration")

    # Service providers
    source_service, _ = tx_models.ServiceProvider.objects.get_or_create(
        name="playground:source",
        audience_id=os.environ.get("PLAYGROUND_SOURCE_OIDC_RP_CLIENT_ID"),
    )
    target_service, _ = tx_models.ServiceProvider.objects.get_or_create(
        name="playground:target",
        audience_id=os.environ.get("PLAYGROUND_TARGET_OIDC_RP_CLIENT_ID"),
    )

    # Credentials
    source_service_credentials, _ = tx_models.ServiceProviderCredentials.objects.get_or_create(
        service_provider=source_service,
        client_id=os.environ.get("TOKEN_EXCHANGE_DEMO_SOURCE_CLIENT_ID"),
    )
    source_service_credentials.set_client_secret(
        os.environ.get("TOKEN_EXCHANGE_DEMO_SOURCE_CLIENT_SECRET", ""), save=True
    )
    target_service_credentials, _ = tx_models.ServiceProviderCredentials.objects.get_or_create(
        service_provider=target_service,
        client_id=os.environ.get("TOKEN_EXCHANGE_DEMO_TARGET_CLIENT_ID"),
    )
    target_service_credentials.set_client_secret(
        os.environ.get("TOKEN_EXCHANGE_DEMO_TARGET_CLIENT_SECRET", ""), save=True
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
        source_scope="target:item:read",
        granted_scope="target:item:read",
    )
    tx_models.ScopeGrant.objects.get_or_create(
        rule=source_to_target_rule,
        source_scope="target:item:write",
        granted_scope="target:item:write",
    )

    # Actions
    target_write_action, _ = tx_models.ActionScope.objects.get_or_create(
        name="action:write-item-to-target",
    )
    tx_models.ActionScopeGrant.objects.get_or_create(
        action=target_write_action,
        target_service=target_service,
        granted_scope="target:item:write",
    )
    target_read_action, _ = tx_models.ActionScope.objects.get_or_create(
        name="action:read-target-item",
    )
    tx_models.ActionScopeGrant.objects.get_or_create(
        action=target_read_action,
        target_service=target_service,
        granted_scope="target:item:read",
    )
    tx_models.TokenExchangeActionPermission.objects.get_or_create(
        rule=source_to_target_rule,
        action=target_write_action,
    )

    create_lasuite_demo(stdout)


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
