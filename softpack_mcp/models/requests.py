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


class SpackSearchRequest(BaseModel):
    """Request to search for spack packages."""

    query: str = Field(..., description="Search query for packages")
    limit: int | None = Field(10, description="Maximum number of results")
