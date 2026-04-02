"""Target: core API views."""

import logging
from datetime import UTC, datetime

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from ..models import Item

logger = logging.getLogger(__name__)


@api_view(
    [
        "GET",
    ]
)
def new_items(request):
    """Check if there are new items since a particular timestamp."""
    since = request.query_params.get("since")
    if since is None:
        return Response(
            {"error": "The 'since' query parameter is missing"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        since = float(since) / 1000.0  # JS now() is in ms
    except ValueError:
        return Response(
            {"error": "The 'since' query parameter is expected to be a float (in ms)"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    since_dt = datetime.fromtimestamp(since, tz=UTC)
    new_items = Item.objects.filter(created_at__gte=since_dt).count()
    if not new_items:
        return Response(
            {"error": "No new item found"}, status=status.HTTP_404_NOT_FOUND
        )

    return Response({"message": f"Found {new_items} new items"})
