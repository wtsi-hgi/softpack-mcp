"""
Main FastAPI application for Softpack MCP server.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger  # noqa: E402

from .config import get_settings  # noqa: E402
from .tools.access import router as access_router  # noqa: E402
from .tools.git import router as git_router  # noqa: E402
from .tools.recipes import router as recipes_router  # noqa: E402
from .tools.sessions import router as sessions_router  # noqa: E402
from .tools.spack import router as spack_router  # noqa: E402
from .utils.exceptions import setup_exception_handlers  # noqa: E402
from .utils.logging import setup_logging  # noqa: E402


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
    app.include_router(access_router, prefix="/access", tags=["access"])
    app.include_router(spack_router, prefix="/spack", tags=["spack"])
    app.include_router(git_router, prefix="/git", tags=["git"])
    app.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
    app.include_router(recipes_router, prefix="/recipes", tags=["recipes"])

    @app.get("/health", operation_id="health_check")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "softpack-mcp"}

    return app


# Application instance
app = create_app()
