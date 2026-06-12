"""Menshen: serializers the token_exchange application."""

from rest_framework import serializers


class TokenRevocationSerializer(serializers.Serializer):
    """
    Serializer for RFC 7009 token revocation requests.

    Validates the token revocation request parameters.
    """

    token = serializers.CharField(required=True)
    token_type_hint = serializers.CharField(required=False, allow_blank=True)

    def validate_token(self, value: str) -> str:
        """Validate that token is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Token cannot be empty")
        return value.strip()
