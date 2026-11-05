"""Menshen: logging tests."""

import datetime
import json
import logging
import re
from types import SimpleNamespace

import pytest
import structlog

from menshen.logging import (
    EventDict,
    get_logging_config,
    json_default,
    wrap_for_formatter,
)
from menshen.settings import Base, Development


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

    if json_renderer:
        event = json.loads(rendered)
        assert event["event"] == "GET /__heartbeat__ 200"
        assert event["logger"] == "request.summary"
        assert event["level"] == "info"
        assert "timestamp" in event
    else:
        # Strip ANSI color codes before matching the console rendering.
        rendered = re.sub(r"\x1b\[[0-9;]*m", "", rendered)
        assert re.fullmatch(
            r"\S+Z \[info\s*\] GET /__heartbeat__ 200\s+\[request.summary\]",
            rendered,
        )


def test_foreign_log_record_extras_are_filtered():
    """Test that only allowed extras of third-party records are rendered."""
    config = get_logging_config(json_renderer=True)
    formatter_config = config["formatters"]["structlog"]
    formatter = formatter_config["()"](
        processors=formatter_config["processors"],
        foreign_pre_chain=formatter_config["foreign_pre_chain"],
    )
    record = logging.LogRecord(
        name="django.request",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Not Found: %s",
        args=("/missing/",),
        exc_info=None,
    )
    record.request = object()
    record.status_code = 404
    record.color_message = "\x1b[33mNot Found\x1b[0m"

    event = json.loads(formatter.format(record))
    assert event["status_code"] == 404
    assert "request" not in event
    assert "color_message" not in event


def test_get_logging_config_defaults():
    """Test that the logging configuration defaults are consistent."""
    config = get_logging_config(json_renderer=True)
    assert config["version"] == 1
    assert config["disable_existing_loggers"] is False
    assert config["handlers"]["console"]["formatter"] == "structlog"
    assert config["root"] == {"handlers": ["console"]}
    assert config["loggers"] == {}


def test_get_logging_config_root_level_and_loggers():
    """Test that the root level and loggers are included in the configuration."""
    loggers = {"token_exchange": {"handlers": ["console"], "level": "INFO"}}
    config = get_logging_config(json_renderer=False, root_level="WARNING", loggers=loggers)
    assert config["root"]["level"] == "WARNING"
    assert config["loggers"]["token_exchange"] == loggers["token_exchange"]


def test_development_logging_shares_base_loggers():
    """Test that the development and base logging configure the same loggers."""
    assert Development.LOGGING["root"] == Base.LOGGING["root"]
    assert Development.LOGGING["loggers"] == Base.LOGGING["loggers"]
    assert {"token_exchange", "lasuite"} <= set(Base.LOGGING["loggers"])


def _structlog_record(event_dict, level=logging.INFO):
    """Build a log record as emitted by structlog through `wrap_for_formatter`."""
    (msg,), kwargs = wrap_for_formatter(logging.getLogger("test"), "info", event_dict)
    record = logging.LogRecord(
        name="django_structlog.middlewares.request",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    record.__dict__.update(kwargs["extra"])
    return record


def test_wrap_for_formatter_message_is_event():
    """Test that structlog records expose the event as message (e.g. for Sentry grouping)."""
    record = _structlog_record(
        {"event": "token_introspection_failed", "timestamp": "2026-11-04T12:00:00Z"}
    )
    assert isinstance(record.msg, EventDict)
    assert str(record.msg) == "token_introspection_failed"
    assert record.getMessage() == "token_introspection_failed"


@pytest.mark.parametrize("json_renderer", [True, False])
def test_structlog_record_is_formatted(json_renderer):
    """Test that structlog records are still rendered with all their fields."""
    config = get_logging_config(json_renderer=json_renderer)
    formatter_config = config["formatters"]["structlog"]
    formatter = formatter_config["()"](
        processors=formatter_config["processors"],
        foreign_pre_chain=formatter_config["foreign_pre_chain"],
    )
    record = _structlog_record({"event": "token_exchanged", "sub": "abc"})
    rendered = re.sub(r"\x1b\[[0-9;]*m", "", formatter.format(record))

    if json_renderer:
        assert json.loads(rendered) == {"event": "token_exchanged", "sub": "abc"}
    else:
        assert "token_exchanged" in rendered
        assert "sub=abc" in rendered


def test_json_renderer_serializes_datetimes():
    """Test that the JSON renderer serializes datetimes to ISO 8601."""
    renderer = structlog.processors.JSONRenderer(default=json_default)
    expires_at = datetime.datetime(2026, 11, 4, 12, 0, tzinfo=datetime.UTC)
    rendered = renderer(None, "info", {"event": "token_exchanged", "expires_at": expires_at})
    assert json.loads(rendered)["expires_at"] == "2026-11-04T12:00:00+00:00"


def test_json_default_falls_back_to_repr():
    """Test that other non-serializable objects are rendered with repr()."""
    obj = object()
    assert json_default(obj) == repr(obj)


def test_request_logs_bind_user_id(client, caplog, monkeypatch):
    """Test that request logs carry the id of the authenticated user."""
    user = SimpleNamespace(pk=42, is_authenticated=True, is_active=True)
    monkeypatch.setattr("django.contrib.auth.get_user", lambda request: user)
    caplog.set_level(logging.INFO, logger="django_structlog")

    client.get("/__version__/")

    events = {
        record.msg["event"]: record.msg
        for record in caplog.records
        if isinstance(record.msg, dict) and record.name.startswith("django_structlog")
    }
    assert events["request_started"]["user_id"] == 42
    assert events["request_finished"]["user_id"] == 42


def _raise():
    """Raise an exception to log."""
    raise ValueError("boom")


@pytest.mark.parametrize("exc_info_value", ["true", "exception", "tuple"])
def test_wrap_for_formatter_passes_exc_info(exc_info_value):
    """Test that exceptions are passed to the stdlib record (e.g. for Sentry)."""
    try:
        _raise()
    except ValueError as raised:
        error = raised
        exc_info = {
            "true": True,
            "exception": error,
            "tuple": (ValueError, error, error.__traceback__),
        }[exc_info_value]
        (msg,), kwargs = wrap_for_formatter(
            logging.getLogger("test"), "error", {"event": "failed", "exc_info": exc_info}
        )

    assert kwargs["exc_info"] == (ValueError, error, error.__traceback__)
    assert msg["exc_info"] == kwargs["exc_info"]


def test_wrap_for_formatter_without_exception():
    """Test that `exc_info=True` outside of an exception handler is dropped."""
    (msg,), kwargs = wrap_for_formatter(
        logging.getLogger("test"), "error", {"event": "failed", "exc_info": True}
    )
    assert "exc_info" not in kwargs
    assert "exc_info" not in msg


@pytest.mark.parametrize("json_renderer", [True, False])
def test_structlog_exception_is_rendered(json_renderer):
    """Test that exceptions of structlog events are rendered with their traceback."""
    config = get_logging_config(json_renderer=json_renderer)
    formatter_config = config["formatters"]["structlog"]
    formatter = formatter_config["()"](
        processors=formatter_config["processors"],
        foreign_pre_chain=formatter_config["foreign_pre_chain"],
    )
    try:
        _raise()
    except ValueError:
        (msg,), kwargs = wrap_for_formatter(
            logging.getLogger("test"), "error", {"event": "failed", "exc_info": True}
        )
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=kwargs["exc_info"],
    )
    record.__dict__.update(kwargs["extra"])
    rendered = formatter.format(record)

    if json_renderer:
        exception = json.loads(rendered)["exception"]
    else:
        exception = re.sub(r"\x1b\[[0-9;]*m", "", rendered)
    assert "Traceback (most recent call last)" in exception
    assert "ValueError: boom" in exception
    # The traceback is not appended a second time by the stdlib formatter.
    assert rendered.count("ValueError: boom") == 1


@pytest.mark.parametrize("enabled", [False, True])
def test_request_started_user_agent(client, caplog, settings, enabled):
    """Test that the user agent is only logged when enabled."""
    settings.LOGGING_USER_AGENT_ENABLED = enabled
    caplog.set_level(logging.INFO, logger="django_structlog")

    client.get("/__version__/", headers={"user-agent": "test-agent/1.0"})

    (event,) = [
        record.msg
        for record in caplog.records
        if isinstance(record.msg, dict) and record.msg["event"] == "request_started"
    ]
    if enabled:
        assert event["user_agent"] == "test-agent/1.0"
    else:
        assert "user_agent" not in event
