"""
Request models for the Softpack MCP Server.
"""

from pydantic import BaseModel, Field


# Spack Request Models
class SpackInstallRequest(BaseModel):
    """Request to install a spack package."""

    package_name: str = Field(..., description="Name of the package to install")
    version: str | None = Field(None, description="Specific version to install")
    variants: list[str] | None = Field(default_factory=list, description="Package variants")
    dependencies: list[str] | None = Field(default_factory=list, description="Additional dependencies")
    session_id: str | None = Field(None, description="Session ID for isolated execution")


class SpackSearchRequest(BaseModel):
    """Request to search for spack packages."""

    query: str = Field(..., description="Search query for packages")
    limit: int | None = Field(10, description="Maximum number of results")
    session_id: str | None = Field(None, description="Session ID for isolated execution")


# Recipe Request Models
class RecipeWriteRequest(BaseModel):
    """Request to write a recipe file."""

    content: str = Field(..., description="Recipe file content (Python code)")
    description: str | None = Field(None, description="Optional description of the recipe")


class RecipeValidateRequest(BaseModel):
    """Request to validate a recipe file."""

    content: str = Field(..., description="Recipe file content to validate")
    package_name: str = Field(..., description="Package name for validation context")


class SpackCreatePypiRequest(BaseModel):
    """Request to create a PyPI package using PyPackageCreator."""

    package_name: str = Field(..., description="Name of the PyPI package to create")
    session_id: str | None = Field(None, description="Session ID for isolated execution")


class SpackCopyPackageRequest(BaseModel):
    """Request to copy an existing spack package without using spack create."""

    package_name: str = Field(..., description="Name of the package to copy")
    session_id: str = Field(..., description="Session ID for isolated execution")


class SpackVersionsRequest(BaseModel):
    """Request to get available versions of a spack package."""

    package_name: str = Field(..., description="Name of the package to get versions for")
    session_id: str | None = Field(None, description="Session ID for isolated execution")


class SpackChecksumRequest(BaseModel):
    """Request to get checksums for a spack package."""

    package_name: str = Field(..., description="Name of the package to get checksums for")
    session_id: str | None = Field(None, description="Session ID for isolated execution")


class SpackCreateFromUrlRequest(BaseModel):
    """Request to create a spack recipe from a URL."""

    url: str = Field(..., description="URL to create recipe from")
    session_id: str | None = Field(None, description="Session ID for isolated execution")


class SpackValidateRequest(BaseModel):
    """Request to validate a spack package installation."""

    package_name: str = Field(..., description="Name of the package to validate")
    package_type: str = Field(default="python", description="Type of package (python, r, other)")
    installation_digest: str | None = Field(None, description="Installation digest hash from the installation step")
    custom_validation_script: str | None = Field(None, description="Custom validation script to use instead of default")
    session_id: str | None = Field(None, description="Session ID for isolated execution")


class GitCommitInfoRequest(BaseModel):
    """Request to get git commit information for a repository."""

    repo_url: str = Field(..., description="Repository URL to get commit info from")
    session_id: str | None = Field(None, description="Session ID for isolated execution")
    package_name: str = Field(..., description="Name of the package to update/create in the session")


class GitPullRequestRequest(BaseModel):
    """Request to create a git pull request."""

    package_name: str = Field(..., description="Name of the package for the PR")
    recipe_name: str | None = Field(None, description="Recipe name (defaults to package_name with prefix)")
    session_id: str = Field(..., description="Session ID for isolated execution")


class GitPullRequest(BaseModel):
    """Request to pull updates from spack-repo."""

    repo_path: str | None = Field(None, description="Path to repository (defaults to ~/spack-repo)")


class SpackUninstallAllRequest(BaseModel):
    """Request to uninstall a spack package and all its dependents."""

    package_name: str = Field(..., description="Name of the package to uninstall")
    session_id: str | None = Field(None, description="Session ID for isolated execution")


class AccessRequestRequest(BaseModel):
    """Request to request collaborator access to spack-repo."""

    github_username: str = Field(..., description="GitHub username requesting access")
    package_name: str = Field(..., description="Name of the package being worked on")
    session_id: str | None = Field(None, description="Session ID for isolated execution")
