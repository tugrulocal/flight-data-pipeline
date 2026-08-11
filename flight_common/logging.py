import json
import logging
import re
from datetime import datetime, timezone


_RESERVED_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}

_SENSITIVE_KEY_PARTS = (
    "authorization",
    "client_secret",
    "credential",
    "password",
    "payload",
    "raw_message",
    "raw_payload",
    "secret",
    "token",
)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(client_secret|access_token|refresh_token|password|authorization)"
    r"\s*[=:]\s*([^\s&,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")


def _is_sensitive_key(key):
    normalized = str(key).lower()
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _sanitize_text(value):
    redacted = _SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}=[REDACTED]",
        value,
    )
    return _BEARER_PATTERN.sub("Bearer [REDACTED]", redacted)


def _sanitize_value(value, key=None):
    if key is not None and _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            nested_key: _sanitize_value(nested_value, nested_key)
            for nested_key, nested_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


class JsonFormatter(logging.Formatter):
    """Servis loglarını secret içermeyen tek satırlık JSON'a dönüştürür."""

    def __init__(self, service):
        super().__init__()
        self.service = service

    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "event": getattr(record, "event", "log"),
            "logger": record.name,
            "message": _sanitize_text(record.getMessage()),
        }

        for key, value in record.__dict__.items():
            if (
                key not in _RESERVED_LOG_RECORD_FIELDS
                and key != "event"
                and not key.startswith("_")
            ):
                payload[key] = _sanitize_value(value, key)

        if record.exc_info:
            payload["exception"] = _sanitize_text(
                self.formatException(record.exc_info)
            )

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging(service, level=logging.INFO):
    """Root logger'ı idempotent biçimde yapılandırır."""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
