"""Menshen: test fixtures for the menshen application."""

import pytest
import structlog


@pytest.fixture(autouse=True)
def clear_structlog_contextvars():
    """Prevent structlog context variables from leaking between tests."""
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()
