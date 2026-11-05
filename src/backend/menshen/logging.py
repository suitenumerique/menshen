"""Structured logging configuration for the menshen project."""

import datetime
import logging
import sys
from typing import Any, cast
from urllib.parse import urlsplit

import structlog
from django.conf import settings
from structlog.typing import Processor

# `extra` attributes of third-party records added to the event. Other extras
# are dropped as they may not be serializable or contain personal data, e.g.
# Django's `request` object (including the query string) or SQL `params`.
EXTRA_ALLOWLIST = ("status_code",)


def get_processors() -> list:
    """
    Return the processors shared by structlog and third-party log records.

    Note that `filter_by_level` is not part of this chain: it requires a
    logger instance which is not available for foreign (non-structlog) records
    in the `ProcessorFormatter`, and level filtering is already performed by
    the standard library before records reach a formatter.

    `wrap_for_formatter` must neither be part of this chain: as the final
    processor of structlog's own chain, it returns a tuple that only
    `ProcessorFormatter` can unpack when rendering structlog events. It is
    appended by `configure_structlog`.

    Exceptions are rendered by the formatter (see `get_logging_config`), so
    that the stdlib record of structlog events keeps its `exc_info` for
    handlers such as Sentry's logging integration (see `wrap_for_formatter`).

    """
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ExtraAdder(allow=EXTRA_ALLOWLIST),
    ]


class EventDict(dict):
    """
    structlog event dict whose string representation is its event message.

    Third-party handlers reading `record.msg` or `record.getMessage()` (e.g.
    Sentry's logging integration, which groups issues by message) get a
    stable message instead of the whole event dict, which contains
    per-record values such as the timestamp or the request id.
    """

    def __str__(self) -> str:
        """Return the event message."""
        return str(self.get("event", ""))


def _resolve_exc_info(exc_info: Any) -> tuple | None:
    """Resolve an `exc_info` event value (`True`, an exception or a tuple) to a tuple."""
    if isinstance(exc_info, BaseException):
        return (type(exc_info), exc_info, exc_info.__traceback__)
    if isinstance(exc_info, tuple):
        return exc_info
    if exc_info:
        exc_info = sys.exc_info()
        return exc_info if exc_info[0] is not None else None
    return None


def wrap_for_formatter(logger: logging.Logger, name: str, event_dict: dict) -> tuple:
    """
    Wrap the event dict like `ProcessorFormatter.wrap_for_formatter`, as an `EventDict`.

    The exception, if any, is also passed to the standard library logger so
    that the record carries it: Sentry's logging integration then reports the
    stack trace and deduplicates the event with the one sent by its Django
    integration for the same exception.
    """
    exc_info = _resolve_exc_info(event_dict.pop("exc_info", None))
    if exc_info is not None:
        event_dict["exc_info"] = exc_info

    args, kwargs = cast(
        "tuple[tuple, dict[str, Any]]",
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter(logger, name, EventDict(event_dict)),
    )
    if exc_info is not None:
        kwargs["exc_info"] = exc_info
    return args, kwargs


def json_default(obj: Any) -> Any:
    """Serialize dates and times to ISO 8601, and other objects to their `repr()`."""
    if isinstance(obj, datetime.date | datetime.time):
        return obj.isoformat()
    return repr(obj)


# Loggers emitting a line per request, already logged by django-structlog's
# `request_started` and `request_finished` events: dockerflow's request
# summary and the uvicorn (production) and runserver (development) access logs.
REQUEST_LOGGERS = ("request.summary", "uvicorn.access", "django.server")


class HealthCheckFilter(logging.Filter):
    """
    Drop successful health check records to reduce development log noise.

    This covers django-structlog's request events for the health check paths
    and the check results logged by dockerflow during heartbeats. Records
    logged at `WARNING` or above are kept so that failing health checks and
    check warnings remain visible.
    """

    def __init__(self, paths: tuple[str, ...] = ("/__heartbeat__", "/__lbheartbeat__")) -> None:
        """Initialize the filter with the request paths to exclude."""
        super().__init__()
        self.paths = {path.rstrip("/") for path in paths}

    def _is_health_check_path(self, path: Any) -> bool:
        """Return whether a request path (possibly with a query string) is a health check."""
        return isinstance(path, str) and urlsplit(path).path.rstrip("/") in self.paths

    def filter(self, record: logging.LogRecord) -> bool:
        """Return whether the record should be logged."""
        if record.levelno >= logging.WARNING:
            return True

        # dockerflow logs the results of the checks run by the heartbeat.
        if record.name == "dockerflow.checks.registry":
            return False

        # django-structlog logs the request as "<METHOD> <full path>". Other
        # request loggers are silenced (see `REQUEST_LOGGERS`).
        request = record.msg.get("request") if isinstance(record.msg, dict) else None
        return not (
            isinstance(request, str) and self._is_health_check_path(request.rpartition(" ")[2])
        )


def get_logging_config(
    json_renderer: bool,
    root_level: str | None = None,
    loggers: dict | None = None,
    filters: dict | None = None,
    handler_filters: list[str] | None = None,
) -> dict:
    """
    Return a logging configuration rendering every record consistently.

    structlog events are rendered by the standard library through a
    `ProcessorFormatter` so that Django, lasuite, uvicorn and any other
    third-party loggers are formatted like structlog events.

    Args:
        json_renderer: render JSON (production) instead of a colored console
            rendering (development).
        root_level: optional level for the root logger.
        loggers: optional configuration for named loggers. The request
            loggers listed in `REQUEST_LOGGERS` are silenced unless
            configured here.
        filters: optional filters declared in the configuration.
        handler_filters: optional filters applied to the console handler.

    """
    renderer = (
        structlog.processors.JSONRenderer(default=json_default)
        if json_renderer
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structlog": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    # The console renderer formats exceptions itself.
                    *([structlog.processors.format_exc_info] if json_renderer else []),
                    renderer,
                ],
                "foreign_pre_chain": get_processors(),
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "structlog",
            },
            "null": {
                "class": "logging.NullHandler",
            },
        },
        "root": {"handlers": ["console"]},
        # Silence request loggers duplicating django-structlog's request events.
        # The CRITICAL level also keeps their errors away from Sentry, which
        # already receives the request exceptions from its Django integration.
        "loggers": {
            name: {"handlers": ["null"], "level": "CRITICAL", "propagate": False}
            for name in REQUEST_LOGGERS
        },
    }

    if root_level is not None:
        cast("dict[str, Any]", config["root"])["level"] = root_level
    if loggers is not None:
        config["loggers"].update(loggers)
    if filters is not None:
        config["filters"] = filters
    if handler_filters is not None:
        cast("dict[str, Any]", config["handlers"]["console"])["filters"] = handler_filters

    return config


def drop_user_agent(sender, log_kwargs: dict, **kwargs) -> None:
    """
    Remove the user agent from django-structlog's `request_started` event.

    The user agent can help fingerprint clients (personal data): it is only
    logged when the `LOGGING_USER_AGENT_ENABLED` setting is enabled.
    Connected to the `bind_extra_request_metadata` signal.
    """
    if not settings.LOGGING_USER_AGENT_ENABLED:
        log_kwargs.pop("user_agent", None)


def configure_structlog() -> None:
    """Configure structlog processors to be rendered by the standard library."""
    structlog.configure(
        processors=cast(
            "list[Processor]",
            [
                # Unlike the foreign_pre_chain, the stdlib logger instance is
                # available here, allowing level filtering to avoid running
                # possibly expensive processors on dropped events.
                structlog.stdlib.filter_by_level,
                *get_processors(),
                wrap_for_formatter,
            ],
        ),
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
