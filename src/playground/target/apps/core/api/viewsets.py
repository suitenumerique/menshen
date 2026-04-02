"""Target: core API viewsets."""

from mozilla_django_oidc.contrib.drf import OIDCAuthentication
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..models import Item
from .authentication import TokenExchangeAuthentication
from .serializers import ItemSerializer


class ItemViewSet(viewsets.ModelViewSet):
    """Item viewset."""

    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    authentication_classes = [TokenExchangeAuthentication]
    permission_classes = [IsAuthenticated]
