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
    install_details: dict[str, Any] | None = Field(None, description="Installation details")


class SpackInstallStreamResult(BaseModel):
    """Streaming result for spack package installation."""

    type: str = Field(..., description="Type of stream event (output, error, complete)")
    data: str = Field(..., description="Stream data content")
    timestamp: float = Field(..., description="Unix timestamp of the event")
    package_name: str = Field(..., description="Name of the package being installed")
    version: str | None = Field(None, description="Package version being installed")
    success: bool | None = Field(None, description="Installation success status (only for complete events)")


class SpackSearchResult(BaseModel):
    """Result of spack package search."""

    packages: list[SpackPackage] = Field(default_factory=list, description="Found packages")
    total: int = Field(..., description="Total number of results")
    query: str = Field(..., description="Original search query")


# Recipe Response Models
class RecipeInfo(BaseModel):
    """Information about a recipe file."""

    package_name: str = Field(..., description="Package name")
    file_path: str = Field(..., description="Relative path to recipe file")
    exists: bool = Field(..., description="Whether the recipe file exists")
    size: int | None = Field(None, description="File size in bytes")
    modified: float | None = Field(None, description="Last modified timestamp")


class RecipeContent(BaseModel):
    """Recipe file content and metadata."""

    package_name: str = Field(..., description="Package name")
    content: str = Field(..., description="Recipe file content")
    file_path: str = Field(..., description="Relative path to recipe file")
    size: int = Field(..., description="File size in bytes")
    modified: float = Field(..., description="Last modified timestamp")


class RecipeListResult(BaseModel):
    """Result of listing recipes in a session."""

    session_id: str = Field(..., description="Session ID")
    recipes: list[RecipeInfo] = Field(default_factory=list, description="List of recipe files")
    total: int = Field(..., description="Total number of recipe files")


class RecipeValidationResult(BaseModel):
    """Result of recipe validation."""

    package_name: str = Field(..., description="Package name")
    is_valid: bool = Field(..., description="Whether the recipe is valid")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    syntax_valid: bool = Field(..., description="Whether Python syntax is valid")


class SpackCreatePypiResult(OperationResult):
    """Result of PyPI package creation."""

    package_name: str = Field(..., description="Name of the created package")
    recipe_path: str | None = Field(None, description="Path to the created recipe file")
    moved_to: str | None = Field(None, description="Destination path where package was moved")
    creation_details: dict[str, Any] | None = Field(None, description="Creation process details")


class SpackCopyPackageResult(OperationResult):
    """Result of copying an existing spack package."""

    package_name: str = Field(..., description="Name of the copied package")
    source_path: str | None = Field(None, description="Source path of the original package")
    destination_path: str | None = Field(None, description="Destination path in session")
    recipe_path: str | None = Field(None, description="Path to the copied recipe file")
    copy_details: dict[str, Any] | None = Field(None, description="Copy process details")
