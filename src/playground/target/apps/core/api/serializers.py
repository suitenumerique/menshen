"""Target: core API serializers."""

from rest_framework import serializers

from ..models import Item


class ItemSerializer(serializers.ModelSerializer):
    """Target Item serializer."""

    class Meta:
        """Meta options."""

        model = Item
        fields = "__all__"
