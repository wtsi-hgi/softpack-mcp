"""
Main FastAPI application with MCP integration.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP

from .config import get_settings
from .tools import spack_router
from .utils.exceptions import setup_exception_handlers
from .utils.logging import setup_logging

# Initialize settings
settings = get_settings()

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    logger.info("Starting Softpack MCP Server...")

    # Startup
    try:
        # Initialize any required services here
        logger.info("All services initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down Softpack MCP Server...")


# Create FastAPI application
app = FastAPI(
    title="Softpack MCP Server",
    description="FastAPI-based MCP server for softpack to interface with spack commands",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup exception handlers
setup_exception_handlers(app)

# Create MCP server instance
mcp = FastApiMCP(app)

# Include routers
app.include_router(spack_router, prefix="/api/v1/spack", tags=["spack"])

# Mount MCP server
mcp.mount()


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Softpack MCP Server",
        "version": "0.1.0",
        "docs": "/docs",
        "mcp": "/mcp",
    }


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": "2025-01-03T00:00:00Z",
        "services": {
            "fastapi": "running",
            "mcp": "running",
        },
    }


@app.get("/info")
async def server_info() -> dict[str, Any]:
    """Server information endpoint."""
    return {
        "name": "Softpack MCP Server",
        "version": "0.1.0",
        "description": "FastAPI-based MCP server for softpack to interface with spack commands",
        "features": [
            "Spack package building",
            "MCP tool integration",
            "Async/await support",
            "Authentication",
        ],
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "mcp": "/mcp",
            "spack": "/api/v1/spack",
        },
    }
