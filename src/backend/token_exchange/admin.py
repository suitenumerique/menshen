"""Menshen: admin configuration for the token_exchange application."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    ActionScope,
    ActionScopeGrant,
    ExchangedToken,
    ScopeGrant,
    ServiceProvider,
    TokenExchangeActionPermission,
    TokenExchangeRule,
)


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    """Admin interface for service providers."""

    list_display = (
        "name",
        "audience_id",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "audience_id")
    readonly_fields = ("created_at", "updated_at")


STR_MAX_DISPLAY_LENGTH: int = 50


@admin.register(ExchangedToken)
class ExchangedTokenAdmin(admin.ModelAdmin):
    """Admin interface for ExchangedToken model."""

    list_display = [
        "token_display",
        "subject_sub",
        "subject_email",
        "token_type",
        "audiences_display",
        "scope_display",
        "expires_at",
        "revoked_at",
        "status",
        "created_at",
    ]

    list_filter = [
        "token_type",
        ("revoked_at", admin.EmptyFieldListFilter),
        "expires_at",
    ]

    search_fields = [
        "token",
        "subject_sub",
        "subject_email",
        "subject_token_jti",
        "audiences",
    ]

    readonly_fields = [
        "token",
        "jwt_kid",
        "actor_token",
        "may_act",
        "subject_token_jti",
        "subject_token_scope",
        "created_at",
        "status",
    ]

    date_hierarchy = "created_at"

    fieldsets = [
        (
            _("Token Information"),
            {
                "fields": [
                    "token",
                    "token_type",
                    "jwt_kid",
                ]
            },
        ),
        (
            _("User & Scopes"),
            {
                "fields": [
                    "subject_sub",
                    "subject_email",
                    "audiences",
                    "scope",
                    "subject_token_scope",
                ]
            },
        ),
        (
            _("Validity"),
            {
                "fields": [
                    "expires_at",
                    "revoked_at",
                    "is_valid_display",
                    "created_at",
                ]
            },
        ),
        (
            _("Advanced (RFC 8693)"),
            {
                "fields": [
                    "actor_token",
                    "may_act",
                    "subject_token_jti",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    actions = ["revoke_selected_tokens"]

    def has_add_permission(self, request):
        """Disable manual creation - tokens should only be created via API."""
        return False

    @admin.display(description=_("Token"))
    def token_display(self, obj):
        """Display truncated token."""
        if len(obj.token) > STR_MAX_DISPLAY_LENGTH:
            return f"{obj.token[:STR_MAX_DISPLAY_LENGTH]}…"
        return obj.token

    @admin.display(description=_("Audiences"))
    def audiences_display(self, obj):
        """Display audiences as comma-separated list."""
        if not obj.audiences:
            return "-"
        return ", ".join(obj.audiences)

    @admin.display(description=_("Scope"))
    def scope_display(self, obj):
        """Display scope truncated."""
        if not obj.scope:
            return "-"
        if len(obj.scope) > STR_MAX_DISPLAY_LENGTH:
            return f"{obj.scope[:STR_MAX_DISPLAY_LENGTH]}…"
        return obj.scope

    @admin.display(description=_("Status"), boolean=True)
    def status(self, obj):
        """Display validity status with icon."""
        if obj.is_revoked():
            return False
        return obj.is_valid()

    @admin.action(description=_("Revoke selected tokens"))
    def revoke_selected_tokens(self, request, queryset):
        """Bulk action to revoke selected tokens."""
        count = 0
        for token in queryset:
            if not token.is_revoked():
                token.revoke()
                count += 1

        self.message_user(
            request,
            _("%d token(s) have been revoked.") % count,
        )


class ScopeGrantInline(admin.TabularInline):
    """Inline admin for ScopeGrant."""

    model = ScopeGrant
    extra = 1
    fields = ["source_scope", "granted_scope", "throttle_rate"]


class TokenExchangeActionPermissionInline(admin.TabularInline):
    """Inline admin for TokenExchangeActionPermission."""

    model = TokenExchangeActionPermission
    extra = 1
    fields = ["action", "required_source_scope"]
    autocomplete_fields = ["action"]


@admin.register(TokenExchangeRule)
class TokenExchangeRuleAdmin(admin.ModelAdmin):
    """Admin interface for TokenExchangeRule model."""

    list_display = [
        "id",
        "source_service",
        "target_service",
        "exchanged_token_duration",
        "is_active",
        "created_at",
    ]

    list_filter = [
        "is_active",
        "created_at",
    ]

    search_fields = [
        "source_service__name",
        "target_service__name",
    ]

    autocomplete_fields = ["source_service", "target_service"]

    inlines = [ScopeGrantInline, TokenExchangeActionPermissionInline]

    fieldsets = [
        (
            _("Services"),
            {
                "fields": [
                    "source_service",
                    "target_service",
                ]
            },
        ),
        (
            _("Configuration"),
            {
                "fields": [
                    "exchanged_token_duration",
                    "is_active",
                ]
            },
        ),
    ]


@admin.register(ScopeGrant)
class ScopeGrantAdmin(admin.ModelAdmin):
    """Admin interface for ScopeGrant model."""

    list_display = [
        "id",
        "rule",
        "source_scope",
        "granted_scope",
        "throttle_rate",
    ]

    list_filter = [
        "rule__source_service",
        "rule__target_service",
    ]

    search_fields = [
        "source_scope",
        "granted_scope",
        "rule__source_service__name",
        "rule__target_service__name",
    ]

    autocomplete_fields = ["rule"]


class ActionScopeGrantInline(admin.TabularInline):
    """Inline admin for ActionScopeGrant."""

    model = ActionScopeGrant
    extra = 1
    fields = ["target_service", "granted_scope", "throttle_rate"]
    autocomplete_fields = ["target_service"]


@admin.register(ActionScope)
class ActionScopeAdmin(admin.ModelAdmin):
    """Admin interface for ActionScope model."""

    list_display = [
        "id",
        "name",
        "description",
        "created_at",
    ]

    search_fields = [
        "name",
        "description",
    ]

    inlines = [ActionScopeGrantInline]

    fieldsets = [
        (
            None,
            {
                "fields": [
                    "name",
                    "description",
                ]
            },
        ),
    ]


@admin.register(ActionScopeGrant)
class ActionScopeGrantAdmin(admin.ModelAdmin):
    """Admin interface for ActionScopeGrant model."""

    list_display = [
        "id",
        "action",
        "target_service",
        "granted_scope",
        "throttle_rate",
    ]

    list_filter = [
        "target_service",
        "action",
    ]

    search_fields = [
        "action__name",
        "target_service__name",
        "granted_scope",
    ]

    autocomplete_fields = ["action", "target_service"]


@admin.register(TokenExchangeActionPermission)
class TokenExchangeActionPermissionAdmin(admin.ModelAdmin):
    """Admin interface for TokenExchangeActionPermission model."""

    list_display = [
        "id",
        "rule",
        "action",
        "required_source_scope",
    ]

    list_filter = [
        "rule__source_service",
        "rule__target_service",
        "action",
    ]

    search_fields = [
        "action__name",
        "rule__source_service__name",
        "rule__target_service__name",
        "required_source_scope",
    ]

    autocomplete_fields = ["rule", "action"]
