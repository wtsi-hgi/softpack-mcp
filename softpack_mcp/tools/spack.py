"""
Spack MCP tools.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from ..models.requests import (
    SpackBuildInfoRequest,
    SpackInstallRequest,
    SpackSearchRequest,
)
from ..models.responses import (
    OperationResult,
    SpackBuildInfo,
    SpackInstallResult,
    SpackPackage,
    SpackSearchResult,
)
from ..services.spack_service import SpackService, get_spack_service

router = APIRouter()


@router.get("/packages", response_model=SpackSearchResult)
async def list_packages(
    query: str = Query("", description="Search query for packages"),
    limit: int = Query(10, description="Maximum number of packages to return"),
    spack: SpackService = Depends(get_spack_service),
) -> SpackSearchResult:
    """
    List available spack packages.

    Args:
        query: Search query to filter packages
        limit: Maximum number of packages to return

    Returns:
        List of spack packages matching the query.
    """
    try:
        packages = await spack.search_packages(query=query, limit=limit)
        return SpackSearchResult(packages=packages, total_count=len(packages), query=query)
    except Exception as e:
        logger.error("Failed to list packages", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SpackSearchResult)
async def search_packages(
    request: SpackSearchRequest, spack: SpackService = Depends(get_spack_service)
) -> SpackSearchResult:
    """
    Search for spack packages.

    Args:
        request: Search parameters

    Returns:
        List of packages matching the search criteria.
    """
    try:
        packages = await spack.search_packages(query=request.query, limit=request.limit)
        return SpackSearchResult(packages=packages, total_count=len(packages), query=request.query)
    except Exception as e:
        logger.error("Failed to search packages", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/install", response_model=SpackInstallResult)
async def install_package(
    request: SpackInstallRequest, spack: SpackService = Depends(get_spack_service)
) -> SpackInstallResult:
    """
    Install a spack package.

    Args:
        request: Package installation parameters

    Returns:
        Installation result with status and details.
    """
    try:
        result = await spack.install_package(
            package_name=request.package_name,
            version=request.version,
            variants=request.variants,
            dependencies=request.dependencies,
        )
        return SpackInstallResult(
            success=result.success,
            message=result.message,
            package_name=request.package_name,
            version=request.version or "latest",
            install_details=result.details,
        )
    except Exception as e:
        logger.exception("Failed to install package", package=request.package_name, error=str(e))
        return SpackInstallResult(
            success=False,
            message=f"Installation failed: {str(e)}",
            package_name=request.package_name,
            version=request.version or "latest",
            install_details={"error": str(e)},
        )


@router.post("/build-info", response_model=SpackBuildInfo)
async def get_build_info(
    request: SpackBuildInfoRequest, spack: SpackService = Depends(get_spack_service)
) -> SpackBuildInfo:
    """
    Get build information for a spack package.

    Args:
        request: Build info request parameters

    Returns:
        Detailed build information for the package.
    """
    try:
        build_info = await spack.get_build_info(package_name=request.package_name, version=request.version)
        if not build_info:
            raise HTTPException(status_code=404, detail=f"Build info not found for package '{request.package_name}'")
        return SpackBuildInfo(
            package_name=request.package_name,
            version=request.version or "latest",
            build_system=build_info.build_system,
            dependencies=build_info.dependencies,
            build_flags=build_info.build_flags,
            install_path=build_info.install_path,
        )
    except Exception as e:
        logger.error("Failed to get build info", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/packages/{package_name}", response_model=OperationResult)
async def uninstall_package(
    package_name: str,
    version: str | None = Query(None, description="Package version"),
    force: bool = Query(False, description="Force uninstallation"),
    spack: SpackService = Depends(get_spack_service),
) -> OperationResult:
    """
    Uninstall a spack package.

    Args:
        package_name: Package name to uninstall
        version: Optional package version
        force: Force uninstallation even if other packages depend on it

    Returns:
        Operation result with uninstallation status.
    """
    try:
        result = await spack.uninstall_package(package_name=package_name, version=version, force=force)
        spec = package_name
        if version:
            spec += f"@{version}"
        message = f"Successfully uninstalled {spec}" if result else f"Failed to uninstall {spec}"
        return OperationResult(success=result, message=message, details={"package": spec, "force": force})
    except Exception as e:
        logger.error("Failed to uninstall package", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/packages/{package_name}", response_model=SpackPackage)
async def get_package_info(
    package_name: str,
    version: str | None = Query(None, description="Package version"),
    spack: SpackService = Depends(get_spack_service),
) -> SpackPackage:
    """
    Get detailed information about a spack package.

    Args:
        package_name: Name of the package
        version: Optional package version

    Returns:
        Detailed package information.
    """
    try:
        package_info = await spack.get_package_info(package_name=package_name, version=version)
        if not package_info:
            raise HTTPException(status_code=404, detail=f"Package '{package_name}' not found")
        return package_info
    except Exception as e:
        logger.error("Failed to get package info", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compilers", response_model=dict[str, Any])
async def list_compilers(spack: SpackService = Depends(get_spack_service)) -> dict[str, Any]:
    """
    List available compilers.

    Returns:
        Dictionary containing available compilers.
    """
    try:
        return await spack.list_compilers()
    except Exception as e:
        logger.error("Failed to list compilers", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
