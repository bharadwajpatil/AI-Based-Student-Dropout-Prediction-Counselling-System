import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variable to hold the current request_id across async tasks
request_id_ctx: ContextVar[str | None] = ContextVar("request_id_ctx", default=None)


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include request_id if available in context
        req_id = request_id_ctx.get()
        if req_id:
            log_entry["request_id"] = req_id

        # Include exception information if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include any extra fields attached to the record
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_entry.update(record.extra)

        return json.dumps(log_entry)


def setup_logging(app_name: str = "student-dropout-system", debug: bool = False) -> logging.Logger:
    """Configures structured JSON logging for the application."""
    root_logger = logging.getLogger()
    log_level = logging.DEBUG if debug else logging.INFO
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Suppress overly verbose third-party loggers if not in debug
    if not debug:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logger = logging.getLogger(app_name)
    return logger
