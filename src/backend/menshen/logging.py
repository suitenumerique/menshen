"""Structured logging configuration for the menshen project."""

import logging.config

import structlog


def get_processors() -> list:
    """
    Return the processors shared by structlog and third-party log records.

    Note that `filter_by_level` is not part of this chain: it requires a
    logger instance which is not available for foreign (non-structlog) records
    in the `ProcessorFormatter`, and level filtering is already performed by
    the standard library before records reach a formatter.

    `ProcessorFormatter.wrap_for_formatter` must neither be part of this
    chain: as the final processor of structlog's own chain, it returns a
    tuple that only `ProcessorFormatter` can unpack when rendering structlog
    events. It is appended by `configure_structlog`.

    """
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ExtraAdder(),
    ]


def get_logging_config(json_renderer: bool) -> dict:
    """
    Return a logging configuration rendering every record consistently.

    structlog events are rendered by the standard library through a
    `ProcessorFormatter` so that Django, lasuite, uvicorn and any other
    third-party loggers are formatted like structlog events.

    Args:
        json_renderer: render JSON (production) instead of a colored console
            rendering (development).

    """
    renderer = (
        structlog.processors.JSONRenderer()
        if json_renderer
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structlog": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
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
        },
        "root": {"handlers": ["console"]},
    }


def configure_structlog() -> None:
    """Configure structlog processors to be rendered by the standard library."""
    structlog.configure(
        processors=[
            # Unlike the foreign_pre_chain, the stdlib logger instance is
            # available here, allowing level filtering to avoid running
            # possibly expensive processors on dropped events.
            structlog.stdlib.filter_by_level,
            *get_processors(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def setup_logging(json_renderer: bool) -> None:
    """
    Set up structured logging for the application.

    Args:
        json_renderer: render JSON (production) instead of a colored console
            rendering (development).

    """
    configure_structlog()
    logging.config.dictConfig(get_logging_config(json_renderer))
