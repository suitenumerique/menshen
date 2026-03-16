"""Menshen API views tests."""

from rest_framework.test import APIClient


def test_hello():
    """Test the hello API view."""
    client = APIClient()
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello Menshen!"}
