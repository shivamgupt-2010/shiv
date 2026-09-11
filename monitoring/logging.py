"""
Structured JSON and Redacting Logging Engine for ShivAI.
"""
import logging
import json
import contextvars
from datetime import datetime, timezone
from security.redaction import redact_secrets

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RedactingFormatter(logging.Formatter):
    """Formats log records as structured JSON while scrubbing credentials."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = request_id_ctx.get() or getattr(record, "request_id", "")
        raw_msg = record.getMessage()
        safe_msg = redact_secrets(raw_msg)

        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": req_id,
            "message": safe_msg,
        }

        if record.exc_info:
            log_data["exception"] = redact_secrets(self.formatException(record.exc_info))

        return json.dumps(log_data)


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configures root logger with secret redaction and JSON output."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    if log_format == "json":
        console_handler.setFormatter(RedactingFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s] %(message)s")
        )

    root_logger.addHandler(console_handler)

    # Quieten verbose third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
