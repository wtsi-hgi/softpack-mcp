"""
Main FastAPI application for Softpack MCP server.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from loguru import logger

from .config import get_settings
from .tools.spack import router as spack_router
from .utils.exceptions import setup_exception_handlers
from .utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting Softpack MCP server")

    yield

    logger.info("Shutting down Softpack MCP server")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Softpack MCP Server",
        description="FastAPI-based MCP server for Softpack spack building commands",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    setup_exception_handlers(app)

    # Include routers
    app.include_router(spack_router, prefix="/spack", tags=["spack"])

    @app.get("/health", operation_id="health_check")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "softpack-mcp"}

    return app


# Application instance
app = create_app()

# create and mount the mcp server
mcp_server = FastApiMCP(app)
mcp_server.mount()
