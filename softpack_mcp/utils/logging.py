"""
Logging configuration using loguru.
"""

import sys
from pathlib import Path
from typing import Any

from loguru import logger


def setup_logging(log_level: str = "info") -> None:
    """
    Setup loguru logging configuration.

    Args:
        log_level: Logging level (trace, debug, info, success, warning, error, critical)
    """
    # Remove default handler
    logger.remove()

    # Normalize log level
    level = log_level.upper()
    if level not in ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]:
        level = "INFO"

    # Console handler with colored output
    logger.add(
        sys.stdout,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        ),
        colorize=True,
    )

    # File handler with detailed information
    log_file = Path("softpack_mcp.log")
    logger.add(
        log_file,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="10 MB",
        retention="1 month",
        compression="gz",
        serialize=False,
    )

    # Configure third-party loggers to use loguru
    import logging

    class InterceptHandler(logging.Handler):
        """Intercept standard logging and redirect to loguru."""

        def emit(self, record):
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = sys._getframe(6), 6
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

    # Intercept all standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Suppress noisy loggers in production
    if level not in ["DEBUG", "TRACE"]:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str):
    """
    Get a loguru logger instance.

    Args:
        name: Logger name (will be prefixed with softpack_mcp)

    Returns:
        Logger instance bound with name context
    """
    return logger.bind(name=f"softpack_mcp.{name}")


class StructuredLogger:
    """Structured logger with additional context using loguru."""

    def __init__(self, name: str):
        """Initialize structured logger."""
        self.logger = logger.bind(name=f"softpack_mcp.{name}")
        self.context: dict[str, Any] = {}

    def add_context(self, **kwargs: Any) -> None:
        """Add context to all log messages."""
        self.context.update(kwargs)
        self.logger = self.logger.bind(**self.context)

    def clear_context(self) -> None:
        """Clear logging context."""
        self.context.clear()
        self.logger = logger.bind(name=f"softpack_mcp.{self.logger.bind().context.get('name', 'unknown')}")

    def trace(self, message: str, **kwargs: Any) -> None:
        """Log trace message with context."""
        self.logger.bind(**kwargs).trace(message)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with context."""
        self.logger.bind(**kwargs).debug(message)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with context."""
        self.logger.bind(**kwargs).info(message)

    def success(self, message: str, **kwargs: Any) -> None:
        """Log success message with context."""
        self.logger.bind(**kwargs).success(message)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with context."""
        self.logger.bind(**kwargs).warning(message)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message with context."""
        self.logger.bind(**kwargs).error(message)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message with context."""
        self.logger.bind(**kwargs).critical(message)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self.logger.bind(**kwargs).exception(message)
