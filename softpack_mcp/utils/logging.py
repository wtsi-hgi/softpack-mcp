"""
Logging configuration and utilities.
"""

import logging
import logging.config
import sys
from typing import Any


def setup_logging(log_level: str = "info") -> None:
    """
    Setup application logging configuration.

    Args:
        log_level: Logging level (debug, info, warning, error, critical)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": (
                    "%(asctime)s - %(name)s - %(levelname)s - " "%(filename)s:%(lineno)d - %(funcName)s() - %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "default",
                "level": level,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "softpack_mcp.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "formatter": "detailed",
                "level": level,
            },
        },
        "loggers": {
            "softpack_mcp": {
                "handlers": ["console", "file"],
                "level": level,
                "propagate": False,
            },
            "fastapi": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
    }

    logging.config.dictConfig(config)

    # Set up uvicorn logging
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(level)

    # Suppress some noisy loggers in production
    if log_level.upper() not in ["DEBUG"]:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(f"softpack_mcp.{name}")


class StructuredLogger:
    """Structured logger with additional context."""

    def __init__(self, name: str):
        """Initialize structured logger."""
        self.logger = get_logger(name)
        self.context: dict[str, Any] = {}

    def add_context(self, **kwargs: Any) -> None:
        """Add context to all log messages."""
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """Clear logging context."""
        self.context.clear()

    def _format_message(self, message: str, **kwargs: Any) -> str:
        """Format message with context."""
        full_context = {**self.context, **kwargs}
        if full_context:
            context_str = " | ".join(f"{k}={v}" for k, v in full_context.items())
            return f"{message} | {context_str}"
        return message

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with context."""
        self.logger.debug(self._format_message(message, **kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with context."""
        self.logger.info(self._format_message(message, **kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with context."""
        self.logger.warning(self._format_message(message, **kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message with context."""
        self.logger.error(self._format_message(message, **kwargs))

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message with context."""
        self.logger.critical(self._format_message(message, **kwargs))
