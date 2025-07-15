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
