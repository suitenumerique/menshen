"""Target: core API permissions."""

from rest_framework import permissions


class TokenExchangeScopePermission(permissions.BasePermission):
    """
    Ensure the exchanged token grants the scopes required by the view.

    The introspected token is available as `request.auth` (see
    `TokenExchangeAuthentication`) and must provide the scopes returned by the
    view's `get_required_scopes` method for the current request method.
    """

    message = "The exchanged token does not grant the required scope(s) for this operation."

    def has_permission(self, request, view):
        """Check that the token scopes satisfy the view's required scopes."""
        required_scopes = view.get_required_scopes(request.method)
        if not required_scopes:
            return True

        token_scopes = set((getattr(request.auth, "scope", "") or "").split())
        return required_scopes.issubset(token_scopes)
