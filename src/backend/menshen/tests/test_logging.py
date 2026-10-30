"""Menshen: logging tests."""

import logging

import pytest

from menshen.logging import get_logging_config


@pytest.mark.parametrize("json_renderer", [True, False])
def test_foreign_log_record_is_formatted(json_renderer):
    """Test that third-party (non-structlog) log records are formatted."""
    config = get_logging_config(json_renderer=json_renderer)
    formatter_config = config["formatters"]["structlog"]
    formatter = formatter_config["()"](
        processors=formatter_config["processors"],
        foreign_pre_chain=formatter_config["foreign_pre_chain"],
    )
    record = logging.LogRecord(
        name="request.summary",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="GET /__heartbeat__ %s",
        args=(200,),
        exc_info=None,
    )
    rendered = formatter.format(record)
    assert "GET /__heartbeat__ 200" in rendered
