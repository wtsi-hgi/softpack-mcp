"""
Configuration settings for the Softpack MCP Server.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Server settings
    host: str = Field(default="127.0.0.1", description="Host to bind to")
    port: int = Field(default=8000, description="Port to bind to")
    debug: bool = Field(default=False, description="Enable debug mode")
    reload: bool = Field(default=False, description="Enable auto-reload")

    # Security settings
    allowed_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")
    api_key: str = Field(default="", description="API key for authentication")

    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="", description="Log file path")
    log_max_size: int = Field(default=10485760, description="Max log file size in bytes")  # 10MB
    log_backup_count: int = Field(default=5, description="Number of log backup files")

    # Spack settings
    spack_executable: str = Field(default="spack", description="Path to spack executable")
    spack_env: str = Field(default="", description="Default spack environment")
    spack_config_dir: str = Field(default="", description="Spack configuration directory")

    # Command execution settings
    command_timeout: int = Field(default=300, description="Command execution timeout in seconds")
    max_parallel_jobs: int = Field(default=4, description="Maximum parallel jobs for builds")

    # MCP settings
    mcp_server_name: str = Field(default="softpack-mcp", description="MCP server name")
    mcp_server_version: str = Field(default="0.1.0", description="MCP server version")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_prefix": "SOFTPACK_",
        "case_sensitive": False,
    }


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
