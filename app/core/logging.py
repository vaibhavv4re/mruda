"""MRUDA — Structured JSON Logging."""

import logging
import json
import sys
from datetime import datetime, timezone
from app.config import settings


class JSONFormatter(logging.Formatter):
    """Produces structured JSON log lines for production observability."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Attach extra fields if present
        for key in ("endpoint", "entity_id", "duration_ms", "status_code"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        return json.dumps(log_entry)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with structured JSON handler."""
    logger = logging.getLogger(f"mruda.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    return logger
