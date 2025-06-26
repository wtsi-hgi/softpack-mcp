"""
Exception handling utilities.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger


class SoftpackMCPException(Exception):
    """Base exception for Softpack MCP."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        """Initialize exception."""
        self.message = message
        self.code = code
        super().__init__(message)


class PackageNotFoundError(SoftpackMCPException):
    """Raised when a package is not found."""

    def __init__(self, package_name: str):
        """Initialize exception."""
        super().__init__(f"Package '{package_name}' not found", "PACKAGE_NOT_FOUND")


class InstallationError(SoftpackMCPException):
    """Raised when package installation fails."""

    def __init__(self, package_name: str, reason: str):
        """Initialize exception."""
        super().__init__(f"Failed to install '{package_name}': {reason}", "INSTALLATION_FAILED")


class BuildError(SoftpackMCPException):
    """Raised when package build fails."""

    def __init__(self, package_name: str, reason: str):
        """Initialize exception."""
        super().__init__(f"Failed to build '{package_name}': {reason}", "BUILD_FAILED")


class ConfigurationError(SoftpackMCPException):
    """Raised when configuration is invalid."""

    def __init__(self, message: str):
        """Initialize exception."""
        super().__init__(f"Configuration error: {message}", "CONFIGURATION_ERROR")


async def softpack_exception_handler(request: Request, exc: SoftpackMCPException) -> JSONResponse:
    """Handle Softpack MCP exceptions."""
    logger.error("Softpack MCP exception", error=exc.message, code=exc.code, path=request.url.path)
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "type": "SoftpackMCPException",
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""
    logger.warning("HTTP exception", status_code=exc.status_code, detail=exc.detail, path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "type": "HTTPException",
            }
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""
    logger.exception("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
                "type": "InternalServerError",
            }
        },
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Setup custom exception handlers for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(SoftpackMCPException, softpack_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    logger.info("Exception handlers configured")
