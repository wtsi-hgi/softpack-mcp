"""
Response models for the Softpack MCP Server.
"""

from typing import Any

from pydantic import BaseModel, Field


# Base Response Models
class OperationResult(BaseModel):
    """Base result for operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Human readable message")
    details: dict[str, Any] | None = Field(None, description="Additional details")


# Spack Response Models
class SpackPackage(BaseModel):
    """Spack package information."""

    name: str = Field(..., description="Package name")
    version: str = Field(..., description="Package version")
    description: str | None = Field(None, description="Package description")
    homepage: str | None = Field(None, description="Package homepage")
    variants: list[str] | None = Field(default_factory=list, description="Available variants")


class SpackBuildInfo(BaseModel):
    """Spack package build information."""

    package_name: str = Field(..., description="Package name")
    version: str = Field(..., description="Package version")
    build_system: str = Field(..., description="Build system used")
    dependencies: list[str] = Field(default_factory=list, description="Package dependencies")
    build_flags: dict[str, str] | None = Field(None, description="Build flags and options")
    install_path: str | None = Field(None, description="Installation path")


class SpackInstallResult(OperationResult):
    """Result of spack package installation."""

    package_name: str = Field(..., description="Name of the installed package")
    version: str = Field(..., description="Installed version")
    install_path: str | None = Field(None, description="Installation path")


class SpackSearchResult(BaseModel):
    """Result of spack package search."""

    packages: list[SpackPackage] = Field(default_factory=list, description="Found packages")
    total: int = Field(..., description="Total number of results")
    query: str = Field(..., description="Original search query")
