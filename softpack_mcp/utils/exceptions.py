"""
Exception handling utilities.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class SoftpackMCPException(Exception):
    """Base exception for Softpack MCP operations."""

    def __init__(self, message: str, details: dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SoftpackException(SoftpackMCPException):
    """Exception for softpack-related operations."""

    pass


class SpackException(SoftpackMCPException):
    """Exception for spack-related operations."""

    pass


class ConfigurationException(SoftpackMCPException):
    """Exception for configuration-related issues."""

    pass


class CommandExecutionException(SoftpackMCPException):
    """Exception for command execution failures."""

    def __init__(self, message: str, command: str, exit_code: int, stderr: str = ""):
        super().__init__(message)
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        self.details = {"command": command, "exit_code": exit_code, "stderr": stderr}


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Setup custom exception handlers for the FastAPI application.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(SoftpackMCPException)
    async def softpack_mcp_exception_handler(request: Request, exc: SoftpackMCPException) -> JSONResponse:
        """Handle custom Softpack MCP exceptions."""
        logger.error(f"Softpack MCP error: {exc.message}", extra={"details": exc.details})

        return JSONResponse(
            status_code=500,
            content={
                "error": "Softpack MCP Error",
                "message": exc.message,
                "details": exc.details,
                "type": exc.__class__.__name__,
            },
        )

    @app.exception_handler(CommandExecutionException)
    async def command_execution_exception_handler(request: Request, exc: CommandExecutionException) -> JSONResponse:
        """Handle command execution exceptions."""
        logger.error(
            f"Command execution failed: {exc.message}",
            extra={"command": exc.command, "exit_code": exc.exit_code, "stderr": exc.stderr},
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": "Command Execution Failed",
                "message": exc.message,
                "command": exc.command,
                "exit_code": exc.exit_code,
                "stderr": exc.stderr,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle request validation errors."""
        logger.warning(f"Validation error: {exc.errors()}")

        return JSONResponse(
            status_code=422,
            content={"error": "Validation Error", "message": "Request validation failed", "details": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Handle HTTP exceptions."""
        logger.warning(f"HTTP error {exc.status_code}: {exc.detail}")

        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "HTTP Error", "message": exc.detail, "status_code": exc.status_code},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle general exceptions."""
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)

        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "type": exc.__class__.__name__,
            },
        )
