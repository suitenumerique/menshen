"""Menshen: permissions for the token_exchange application."""

from rest_framework.permissions import BasePermission

from .models import ServiceProvider


class IsServiceProviderAuthenticated(BasePermission):
    """Allows access only to authenticated ServiceProvider."""

    def has_permission(self, request, view) -> bool:
        """Check if the user is an authenticated ServiceProvider."""
        return bool(
            request.user
            and isinstance(request.user, ServiceProvider)
            and request.user.is_authenticated
        )
