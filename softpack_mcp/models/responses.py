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
    detailed_failed_log: str | None = Field(
        None, description="Full contents of spack-build-out.txt files if install failed"
    )


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
    has_checksum: bool = Field(False, description="Whether this version has a checksum available")
    checksum: str | None = Field(None, description="SHA256 checksum if available")


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
    install_digest: str | None = Field(None, description="Installation digest hash")
    install_details: dict[str, Any] | None = Field(None, description="Installation details")
    detailed_failed_log: str | None = Field(
        None, description="Full contents of spack-build-out.txt files if install failed"
    )


class SpackInstallStreamResult(BaseModel):
    """Streaming result for spack package installation."""

    type: str = Field(..., description="Type of stream event (output, error, complete)")
    data: str = Field(..., description="Stream data content")
    timestamp: float = Field(..., description="Unix timestamp of the event")
    package_name: str = Field(..., description="Name of the package being installed")
    version: str | None = Field(None, description="Package version being installed")
    success: bool | None = Field(None, description="Installation success status (only for complete events)")
    install_digest: str | None = Field(None, description="Installation digest hash (only for complete events)")
    detailed_failed_log: str | None = Field(
        None, description="Full contents of spack-build-out.txt files if install failed (only for complete events)"
    )


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
    moved_packages: list[dict[str, str]] | None = Field(
        None, description="List of all packages that were moved, including dependencies"
    )
    creation_details: dict[str, Any] | None = Field(None, description="Creation process details")


class SpackCopyPackageResult(OperationResult):
    """Result of copying an existing spack package."""

    package_name: str = Field(..., description="Name of the copied package")
    source_path: str | None = Field(None, description="Source path of the original package")
    destination_path: str | None = Field(None, description="Destination path in session")
    recipe_path: str | None = Field(None, description="Path to the copied recipe file")
    copied_files: list[str] | None = Field(None, description="List of all files copied from the package directory")
    copy_details: dict[str, Any] | None = Field(None, description="Copy process details")


class SpackVersionsResult(OperationResult):
    """Result of getting available versions for a spack package."""

    package_name: str = Field(..., description="Name of the package")
    versions: list[str] = Field(default_factory=list, description="Available versions (deprecated)")
    version_info: list[SpackVersionInfo] = Field(default_factory=list, description="Detailed version information")
    version_details: dict[str, Any] | None = Field(None, description="Additional version information")


class SpackChecksumResult(OperationResult):
    """Result of getting checksums for a spack package."""

    package_name: str = Field(..., description="Name of the package")
    checksums: dict[str, str] = Field(default_factory=dict, description="Version to checksum mapping")
    checksum_details: dict[str, Any] | None = Field(None, description="Additional checksum information")


class SpackCreateFromUrlResult(OperationResult):
    """Result of creating a spack recipe from a URL."""

    url: str = Field(..., description="URL used to create the recipe")
    package_name: str | None = Field(None, description="Detected package name")
    recipe_path: str | None = Field(None, description="Path to the created recipe file")
    creation_details: dict[str, Any] | None = Field(None, description="Creation process details")


class SpackValidationResult(OperationResult):
    """Result of validating a spack package installation."""

    package_name: str = Field(..., description="Name of the validated package")
    package_type: str = Field(..., description="Type of package validated")
    validation_command: str = Field(..., description="Command used for validation")
    validation_output: str | None = Field(None, description="Output from validation command")
    validation_details: dict[str, Any] | None = Field(None, description="Additional validation information")


class SpackValidationStreamResult(BaseModel):
    """Streaming result for spack package validation."""

    type: str = Field(..., description="Type of stream event (output, error, complete)")
    data: str = Field(..., description="Stream data content")
    timestamp: float = Field(..., description="Unix timestamp of the event")
    package_name: str = Field(..., description="Name of the package being validated")
    package_type: str = Field(..., description="Type of package being validated")
    success: bool | None = Field(None, description="Validation success status (only for complete events)")
    validation_command: str | None = Field(None, description="Command used for validation (only for complete events)")


class GitCommitInfoResult(OperationResult):
    """Result of getting git commit information."""

    repo_url: str = Field(..., description="Repository URL")
    commit_hash: str | None = Field(None, description="Latest commit hash")
    commit_date: str | None = Field(None, description="Commit date in YYYYMMDD format")
    commit_details: dict[str, Any] | None = Field(None, description="Additional commit information")


class GitPullRequestResult(OperationResult):
    """Result of creating a git pull request."""

    package_name: str = Field(..., description="Name of the package")
    branch_name: str | None = Field(None, description="Created branch name")
    commit_message: str | None = Field(None, description="Commit message used")
    git_commands: list[str] = Field(default_factory=list, description="Git commands executed")
    pr_url: str | None = Field(None, description="GitHub PR creation URL")
    pr_details: dict[str, Any] | None = Field(None, description="Additional PR creation details")


class SpackUninstallAllResult(OperationResult):
    """Result of uninstalling a spack package and all its dependents."""

    package_name: str = Field(..., description="Name of the uninstalled package")
    uninstalled_packages: list[str] = Field(default_factory=list, description="List of packages that were uninstalled")
    uninstall_details: dict[str, Any] | None = Field(None, description="Additional uninstall information")


class GitPullResult(OperationResult):
    """Result of git pull operation."""

    repository_path: str = Field(..., description="Path to the repository that was updated")
    changes_pulled: bool = Field(..., description="Whether new changes were pulled")
    commit_hash: str | None = Field(None, description="Latest commit hash after pull")
    pull_details: dict[str, Any] | None = Field(None, description="Additional pull information")


class AccessRequestResult(OperationResult):
    """Result of collaborator access request."""

    github_username: str = Field(..., description="GitHub username that requested access")
    package_name: str = Field(..., description="Name of the package being worked on")
    email_sent: bool = Field(..., description="Whether the access request email was sent successfully")
    email_details: dict[str, Any] | None = Field(None, description="Additional email sending details")
