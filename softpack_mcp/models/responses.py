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
class SpackVariant(BaseModel):
    """Spack package variant information."""

    name: str = Field(..., description="Variant name")
    default: str | bool | None = Field(None, description="Default value")
    values: list[str] | None = Field(default_factory=list, description="Possible values")
    description: str | None = Field(None, description="Variant description")
    conditional: str | None = Field(None, description="Conditional expression (when clause)")


class SpackVersionInfo(BaseModel):
    """Spack package version information."""

    version: str = Field(..., description="Version number")
    url: str | None = Field(None, description="Download URL")


class SpackDependencyInfo(BaseModel):
    """Spack package dependency information."""

    name: str = Field(..., description="Dependency package name")
    type: str = Field(..., description="Dependency type (build, link, run)")
    when: str | None = Field(None, description="Conditional expression")


class SpackPackage(BaseModel):
    """Comprehensive spack package information."""

    name: str = Field(..., description="Package name")
    version: str = Field(..., description="Package version")
    package_type: str | None = Field(None, description="Package type (e.g., PythonPackage, CMakePackage)")
    description: str | None = Field(None, description="Package description")
    homepage: str | None = Field(None, description="Package homepage")

    # Version information
    preferred_version: SpackVersionInfo | None = Field(None, description="Preferred version")
    safe_versions: list[SpackVersionInfo] | None = Field(default_factory=list, description="Safe versions")
    deprecated_versions: list[SpackVersionInfo] | None = Field(default_factory=list, description="Deprecated versions")

    # Variants with detailed information
    variants: list[SpackVariant] | None = Field(default_factory=list, description="Available variants with details")

    # Dependencies categorized by type
    build_dependencies: list[str] | None = Field(default_factory=list, description="Build dependencies")
    link_dependencies: list[str] | None = Field(default_factory=list, description="Link dependencies")
    run_dependencies: list[str] | None = Field(default_factory=list, description="Run dependencies")

    # License information
    licenses: list[str] | None = Field(default_factory=list, description="Package licenses")

    # Backward compatibility - keeping these for existing code
    dependencies: list[str] | None = Field(
        default_factory=list, description="All dependencies (deprecated, use specific dependency types)"
    )


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
