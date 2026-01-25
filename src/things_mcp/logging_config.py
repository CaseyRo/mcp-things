#!/usr/bin/env python3
"""
Enhanced logging configuration for Things MCP server.
Provides structured logging with multiple outputs and log levels.
"""

import logging
import logging.handlers
import json
import re
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Any, Optional

# Create logs directory if it doesn't exist
LOGS_DIR = Path.home() / ".things-mcp" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

REDACTION_TOKEN = "[REDACTED]"
SENSITIVE_FIELDS = {
    "title",
    "notes",
    "tags",
    "params",
    "query",
    "text",
    "body",
    "content",
    "script",
    "payload",
    "list_title",
    "checklist_items",
    "stderr",
    "stdout",
}


def _is_sensitive_field(field_name: Optional[str]) -> bool:
    return bool(field_name and field_name.lower() in SENSITIVE_FIELDS)


def redact_sensitive_data(value: Any, field_name: Optional[str] = None) -> Any:
    """Redact sensitive values while preserving structural hints."""
    if field_name and _is_sensitive_field(field_name):
        if isinstance(value, dict):
            return {key: redact_sensitive_data(val, key) for key, val in value.items()}
        if isinstance(value, list):
            return [redact_sensitive_data(item, field_name) for item in value]
        if isinstance(value, tuple):
            return tuple(redact_sensitive_data(item, field_name) for item in value)
        if isinstance(value, set):
            return {REDACTION_TOKEN for _ in value}
        if value is None:
            return None
        return REDACTION_TOKEN

    if isinstance(value, dict):
        return {key: redact_sensitive_data(val, key) for key, val in value.items()}
    if isinstance(value, list):
        return [redact_sensitive_data(item, field_name) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item, field_name) for item in value)
    if isinstance(value, set):
        return {redact_sensitive_data(item, field_name) for item in value}
    return value


def sanitize_for_logging(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a copy of data with sensitive fields redacted."""
    if not data:
        return {}
    return {key: redact_sensitive_data(value, key) for key, value in data.items()}


def _redact_message_text(message: str) -> str:
    """Apply conservative redaction to inline messages."""
    patterns = [
        (r"(title\s*[:=]\s*)([^;,.]+)", r"\1" + REDACTION_TOKEN),
        (r"(notes\s*[:=]\s*)([^;,.]+)", r"\1" + REDACTION_TOKEN),
        (r"(tags\s*[:=]\s*)([^;,.]+)", r"\1" + REDACTION_TOKEN),
        (r"(params\s*[:=]\s*)([^;,.]+)", r"\1" + REDACTION_TOKEN),
    ]
    redacted = message
    for pattern, repl in patterns:
        redacted = re.sub(pattern, repl, redacted, flags=re.IGNORECASE)
    return redacted


def _sanitize_record(record: logging.LogRecord) -> None:
    """Redact sensitive values attached to the log record."""
    for key, value in list(vars(record).items()):
        if key in {"args", "msg"}:
            continue
        if _is_sensitive_field(key):
            setattr(record, key, redact_sensitive_data(value, key))
        elif isinstance(value, dict):
            setattr(record, key, sanitize_for_logging(value))

    if isinstance(record.args, dict):
        record.args = sanitize_for_logging(record.args)
    elif isinstance(record.args, tuple):
        record.args = tuple(
            redact_sensitive_data(arg)
            if isinstance(arg, (dict, list, tuple, set))
            else arg
            for arg in record.args
        )

    if isinstance(record.msg, dict):
        record.msg = sanitize_for_logging(record.msg)
    elif isinstance(record.msg, str):
        record.msg = _redact_message_text(record.msg)


class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive information from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        _sanitize_record(record)
        return True


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs for better analysis."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add any extra fields
        if hasattr(record, "operation"):
            log_data["operation"] = record.operation
        if hasattr(record, "duration"):
            log_data["duration"] = record.duration
        if hasattr(record, "error_type"):
            log_data["error_type"] = record.error_type
        if hasattr(record, "retry_count"):
            log_data["retry_count"] = record.retry_count

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class OperationLogFilter(logging.Filter):
    """Filter to add operation context to log records."""

    def __init__(self):
        super().__init__()
        self.operation_context = {}

    def set_operation_context(self, operation: str, **kwargs):
        """Set the current operation context."""
        self.operation_context = {"operation": operation, **kwargs}

    def clear_operation_context(self):
        """Clear the operation context."""
        self.operation_context = {}

    def filter(self, record: logging.LogRecord) -> bool:
        # Add operation context to the record
        for key, value in self.operation_context.items():
            setattr(record, key, value)
        return True


# Global filters
operation_filter = OperationLogFilter()
redaction_filter = SensitiveDataFilter()


def setup_logging(
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    structured_logs: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Configure comprehensive logging for the Things MCP server.

    Args:
        console_level: Log level for console output
        file_level: Log level for file output
        structured_logs: Whether to use structured JSON logging
        max_bytes: Maximum size of log files before rotation
        backup_count: Number of backup files to keep
    """
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything, filter at handler level

    # Remove existing handlers
    root_logger.handlers.clear()
    root_logger.addFilter(redaction_filter)

    # Console handler with simple formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, console_level.upper()))
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    console_handler.addFilter(operation_filter)
    console_handler.addFilter(redaction_filter)
    root_logger.addHandler(console_handler)

    # File handlers with rotation
    if structured_logs:
        # Structured JSON logs for analysis
        json_file_handler = logging.handlers.RotatingFileHandler(
            LOGS_DIR / "things_mcp_structured.json",
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        json_file_handler.setLevel(getattr(logging, file_level.upper()))
        json_file_handler.setFormatter(StructuredFormatter())
        json_file_handler.addFilter(operation_filter)
        json_file_handler.addFilter(redaction_filter)
        root_logger.addHandler(json_file_handler)

    # Human-readable file logs
    text_file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "things_mcp.log", maxBytes=max_bytes, backupCount=backup_count
    )
    text_file_handler.setLevel(getattr(logging, file_level.upper()))
    text_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    text_file_handler.setFormatter(text_format)
    text_file_handler.addFilter(operation_filter)
    text_file_handler.addFilter(redaction_filter)
    root_logger.addHandler(text_file_handler)

    # Error-only file handler
    error_file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "things_mcp_errors.log", maxBytes=max_bytes, backupCount=backup_count
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(text_format)
    error_file_handler.addFilter(operation_filter)
    error_file_handler.addFilter(redaction_filter)
    root_logger.addHandler(error_file_handler)

    # Log the logging configuration
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "console_level": console_level,
            "file_level": file_level,
            "structured_logs": structured_logs,
            "logs_dir": str(LOGS_DIR),
        },
    )


def log_operation_start(operation: str, **kwargs) -> None:
    """Log the start of an operation and set context."""
    sanitized_kwargs = sanitize_for_logging(kwargs)
    operation_filter.set_operation_context(operation, **sanitized_kwargs)
    logger = logging.getLogger(__name__)
    logger.info(
        "Starting operation", extra={"operation": operation, **sanitized_kwargs}
    )


def log_operation_end(
    operation: str, success: bool, duration: float = None, **kwargs
) -> None:
    """Log the end of an operation."""
    logger = logging.getLogger(__name__)
    sanitized_kwargs = sanitize_for_logging(kwargs)
    extra = {"operation": operation, "success": success, **sanitized_kwargs}
    if duration is not None:
        extra["duration"] = duration

    if success:
        logger.info("Operation completed", extra=extra)
    else:
        logger.error("Operation failed", extra=extra)

    operation_filter.clear_operation_context()


def log_retry_attempt(
    operation: str, attempt: int, max_attempts: int, error: str
) -> None:
    """Log a retry attempt."""
    logger = logging.getLogger(__name__)
    logger.warning(
        "Retry attempt",
        extra={
            "operation": operation,
            "retry_count": attempt,
            "max_attempts": max_attempts,
            "error": REDACTION_TOKEN if error else None,
        },
    )


def log_circuit_breaker_state(state: str, failure_count: int = None) -> None:
    """Log circuit breaker state changes."""
    logger = logging.getLogger(__name__)
    extra = {"circuit_breaker_state": state}
    if failure_count is not None:
        extra["failure_count"] = failure_count

    logger.warning("Circuit breaker state changed", extra=extra)


def log_dead_letter_queue(operation: str, params: Dict[str, Any], error: str) -> None:
    """Log when an operation is added to the dead letter queue."""
    logger = logging.getLogger(__name__)
    logger.error(
        "Added to dead letter queue",
        extra={
            "operation": operation,
            "params": redact_sensitive_data(params, "params"),
            "error": REDACTION_TOKEN if error else None,
            "dlq": True,
        },
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


# Initialize logging when module is imported
setup_logging()
