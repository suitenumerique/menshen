"""Target: core API viewsets."""

from rest_framework import viewsets
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated

from ..models import Item
from .authentication import TokenExchangeAuthentication
from .permissions import TokenExchangeScopePermission
from .serializers import ItemSerializer


class ItemViewSet(viewsets.ModelViewSet):
    """Item viewset."""

    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    authentication_classes = [TokenExchangeAuthentication]
    permission_classes = [IsAuthenticated, TokenExchangeScopePermission]

    # Required scopes to read/write objects
    read_scopes: set[str] = {"target:read"}
    write_scopes: set[str] = {"target:write"}

    def get_required_scopes(self, method: str) -> set[str]:
        """
        Return the scopes required on the exchanged token for a request method.

        Safe methods (read) require the `target:read` scope while unsafe methods
        (write: create, update, delete) require the `target:write` scope.
        """
        if method in SAFE_METHODS:
            return self.read_scopes
        return self.write_scopes
