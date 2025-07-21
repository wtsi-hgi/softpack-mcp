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

    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="", description="Log file path")
    log_max_size: int = Field(default=10485760, description="Max log file size in bytes")  # 10MB
    log_backup_count: int = Field(default=5, description="Number of log backup files")

    # Spack settings
    spack_executable: str = Field(default="spack", description="Path to spack executable")

    # Command execution settings
    command_timeout: int = Field(default=300, description="Command execution timeout in seconds")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_prefix": "SOFTPACK_",
        "case_sensitive": False,
        "extra": "ignore",  # Ignore extra fields not defined in the model
    }


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
