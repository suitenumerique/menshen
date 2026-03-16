"""Menshen API views."""

from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def hello(request):
    """A simple API test view to remove."""
    return Response({"message": "Hello Menshen!"})
