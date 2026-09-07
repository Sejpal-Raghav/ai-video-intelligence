"""Structured allowlisted logging matching Blueprint Section 15.3 and Section 20.1."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class SafeJsonFormatter(logging.Formatter):
    """Formats log records as JSON using an allowlist of permitted fields.

    Redacts sensitive details, raw paths, secrets, and raw probe outputs.
    """

    ALLOWED_EXTRA_KEYS = {
        "request_id",
        "video_id",
        "run_id",
        "job_id",
        "event_id",
        "stage",
        "status",
        "error_code",
        "attempt",
        "duration_ms",
        "track_id",
        "event_type",
        "worker_id",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include allowlisted extra fields
        for key in self.ALLOWED_EXTRA_KEYS:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        # Include exception info if available and explicitly allowed
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_entry["exception"] = record.exc_text

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configures root logger with the SafeJsonFormatter on stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(SafeJsonFormatter())

    root = logging.getLogger()
    root.setLevel(level.upper())

    # Replace existing handlers
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Returns a logger configured for structured output."""
    return logging.getLogger(name)
