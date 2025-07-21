"""
Spack MCP tools.
"""

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger

from ..models.requests import (
    SpackChecksumRequest,
    SpackCopyPackageRequest,
    SpackCreateFromUrlRequest,
    SpackCreatePypiRequest,
    SpackInstallRequest,
    SpackSearchRequest,
    SpackUninstallAllRequest,
    SpackValidateRequest,
    SpackVersionsRequest,
)
from ..models.responses import (
    OperationResult,
    SpackChecksumResult,
    SpackCopyPackageResult,
    SpackCreateFromUrlResult,
    SpackCreatePypiResult,
    SpackInstallResult,
    SpackInstallStreamResult,
    SpackPackage,
    SpackSearchResult,
    SpackUninstallAllResult,
    SpackValidationResult,
    SpackVersionsResult,
)
from ..services.spack_service import SpackService, get_spack_service

router = APIRouter()


@router.get("/packages", response_model=SpackSearchResult, operation_id="list_packages")
async def list_packages(
    query: str = Query("", description="Search query for packages"),
    limit: int = Query(10, description="Maximum number of packages to return"),
    session_id: str = Query(None, description="Session ID for isolated execution"),
    spack: SpackService = Depends(get_spack_service),
) -> SpackSearchResult:
    """
    List available spack packages.

    Args:
        query: Search query to filter packages
        limit: Maximum number of packages to return
        session_id: Session ID for isolated execution

    Returns:
        List of spack packages matching the query.
    """
    try:
        packages = await spack.search_packages(query=query, limit=limit, session_id=session_id)
        return SpackSearchResult(packages=packages, total=len(packages), query=query)
    except Exception as e:
        logger.error("Failed to list packages", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SpackSearchResult, operation_id="search_packages")
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
        packages = await spack.search_packages(query=request.query, limit=request.limit, session_id=request.session_id)
        return SpackSearchResult(packages=packages, total=len(packages), query=request.query)
    except Exception as e:
        logger.error("Failed to search packages", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/install", response_model=SpackInstallResult, operation_id="install_package")
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
            session_id=request.session_id,
        )
        return SpackInstallResult(
            success=result.success,
            message=result.message,
            package_name=request.package_name,
            version=request.version or "latest",
            install_digest=result.details.get("install_digest") if result.details else None,
            install_details=result.details,
        )
    except Exception as e:
        logger.exception("Failed to install package", package=request.package_name, error=str(e))
        return SpackInstallResult(
            success=False,
            message=f"Installation failed: {str(e)}",
            package_name=request.package_name,
            version=request.version or "latest",
            install_digest=None,
            install_details={"error": str(e)},
        )


@router.post("/install/stream", operation_id="install_package_stream")
async def install_package_stream(
    request: SpackInstallRequest, spack: SpackService = Depends(get_spack_service)
) -> StreamingResponse:
    """
    Install a spack package with streaming output.

    Args:
        request: Package installation parameters

    Returns:
        Server-Sent Events stream of installation progress.
    """

    async def generate_stream():
        try:
            async for result in spack.install_package_stream(
                package_name=request.package_name,
                version=request.version,
                variants=request.variants,
                dependencies=request.dependencies,
                session_id=request.session_id,
            ):
                # Convert to JSON and send as SSE
                data = json.dumps(result.model_dump())
                yield f"data: {data}\n\n"
        except Exception as e:
            logger.exception("Failed to stream package installation", package=request.package_name, error=str(e))
            error_result = SpackInstallStreamResult(
                type="error",
                data=f"Installation failed: {str(e)}",
                timestamp=time.time(),
                package_name=request.package_name,
                version=request.version,
            )
            data = json.dumps(error_result.model_dump())
            yield f"data: {data}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.delete("/packages/{package_name}", response_model=OperationResult, operation_id="uninstall_package")
async def uninstall_package(
    package_name: str,
    version: str | None = Query(None, description="Package version"),
    force: bool = Query(False, description="Force uninstallation"),
    session_id: str = Query(None, description="Session ID for isolated execution"),
    spack: SpackService = Depends(get_spack_service),
) -> OperationResult:
    """
    Uninstall a spack package.

    Args:
        package_name: Package name to uninstall
        version: Optional package version
        force: Force uninstallation even if other packages depend on it
        session_id: Session ID for isolated execution

    Returns:
        Operation result with uninstallation status.
    """
    try:
        result = await spack.uninstall_package(
            package_name=package_name, version=version, force=force, session_id=session_id
        )
        spec = package_name
        if version:
            spec += f"@{version}"
        message = f"Successfully uninstalled {spec}" if result else f"Failed to uninstall {spec}"
        return OperationResult(success=result, message=message, details={"package": spec, "force": force})
    except Exception as e:
        logger.error("Failed to uninstall package", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/packages/{package_name}", response_model=SpackPackage, operation_id="get_package_info")
async def get_package_info(
    package_name: str,
    version: str | None = Query(None, description="Package version"),
    session_id: str = Query(None, description="Session ID for isolated execution"),
    spack: SpackService = Depends(get_spack_service),
) -> SpackPackage:
    """
    Get comprehensive information about a spack package.

    Includes description, homepage, variants, dependencies, and other details.

    Args:
        package_name: Name of the package
        version: Optional package version
        session_id: Session ID for isolated execution

    Returns:
        Comprehensive package information including build details.
    """
    try:
        package_info = await spack.get_package_info(package_name=package_name, version=version, session_id=session_id)
        if not package_info:
            raise HTTPException(status_code=404, detail=f"Package '{package_name}' not found")
        return package_info
    except Exception as e:
        logger.error("Failed to get package info", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-pypi", response_model=SpackCreatePypiResult, operation_id="create_pypi_package")
async def create_pypi_package(
    request: SpackCreatePypiRequest, spack: SpackService = Depends(get_spack_service)
) -> SpackCreatePypiResult:
    """
    Create a PyPI package using PyPackageCreator.

    This endpoint executes the following workflow:
    1. cd ~/r-spack-recipe-builder
    2. ./PyPackageCreator.py -f {package_name}
    3. mv ~/r-spack-recipe-builder/packages/py-* /tmp/{session_uuid}/packages/ (if session_id provided)

    Args:
        request: PyPI package creation parameters

    Returns:
        Creation result with status and details.
    """
    try:
        result = await spack.create_pypi_package(
            package_name=request.package_name,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        logger.exception("Failed to create PyPI package", package=request.package_name, error=str(e))
        return SpackCreatePypiResult(
            success=False,
            message=f"PyPI package creation failed: {str(e)}",
            package_name=request.package_name,
            creation_details={"error": str(e)},
        )


@router.post("/copy-package", response_model=SpackCopyPackageResult, operation_id="copy_existing_package")
async def copy_existing_package(
    request: SpackCopyPackageRequest, spack: SpackService = Depends(get_spack_service)
) -> SpackCopyPackageResult:
    """
    Copy an existing spack package without using spack create.

    This endpoint mimics the create() function from .zshrc but skips the spack create step.
    It copies an existing package from the builtin packages to the session directory and
    applies the same modifications as the shell function.

    Args:
        request: Package copy parameters

    Returns:
        Copy result with status and details.
    """
    try:
        result = await spack.copy_existing_package(
            package_name=request.package_name,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        logger.exception("Failed to copy package", package=request.package_name, error=str(e))
        return SpackCopyPackageResult(
            success=False,
            message=f"Package copy failed: {str(e)}",
            package_name=request.package_name,
            copy_details={"error": str(e)},
        )


@router.post("/versions", response_model=SpackVersionsResult, operation_id="get_package_versions")
async def get_package_versions(
    request: SpackVersionsRequest, spack: SpackService = Depends(get_spack_service)
) -> SpackVersionsResult:
    """
    Get available versions for a spack package.

    This endpoint executes: spack versions {package_name}

    Args:
        request: Package versions request parameters

    Returns:
        Available versions result with status and details.
    """
    try:
        result = await spack.get_package_versions(
            package_name=request.package_name,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        logger.exception("Failed to get package versions", package=request.package_name, error=str(e))
        return SpackVersionsResult(
            success=False,
            message=f"Failed to get versions: {str(e)}",
            package_name=request.package_name,
            versions=[],
            version_details={"error": str(e)},
        )


@router.post("/checksum", response_model=SpackChecksumResult, operation_id="get_package_checksums")
async def get_package_checksums(
    request: SpackChecksumRequest, spack: SpackService = Depends(get_spack_service)
) -> SpackChecksumResult:
    """
    Get checksums for a spack package.

    This endpoint executes: spack checksum -b {package_name}

    Args:
        request: Package checksum request parameters

    Returns:
        Package checksums result with status and details.
    """
    try:
        result = await spack.get_package_checksums(
            package_name=request.package_name,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        logger.exception("Failed to get package checksums", package=request.package_name, error=str(e))
        return SpackChecksumResult(
            success=False,
            message=f"Failed to get checksums: {str(e)}",
            package_name=request.package_name,
            checksums={},
            checksum_details={"error": str(e)},
        )


@router.post("/create-from-url", response_model=SpackCreateFromUrlResult, operation_id="create_recipe_from_url")
async def create_recipe_from_url(
    request: SpackCreateFromUrlRequest, spack: SpackService = Depends(get_spack_service)
) -> SpackCreateFromUrlResult:
    """
    Create a spack recipe from a URL.

    This endpoint executes: spack create --skip-editor -b {url}

    Args:
        request: Recipe creation from URL parameters

    Returns:
        Recipe creation result with status and details.
    """
    try:
        result = await spack.create_recipe_from_url(
            url=request.url,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        logger.exception("Failed to create recipe from URL", url=request.url, error=str(e))
        return SpackCreateFromUrlResult(
            success=False,
            message=f"Failed to create recipe from URL: {str(e)}",
            url=request.url,
            creation_details={"error": str(e)},
        )


@router.post("/validate", response_model=SpackValidationResult, operation_id="validate_package")
async def validate_package(
    request: SpackValidateRequest, spack: SpackService = Depends(get_spack_service)
) -> SpackValidationResult:
    """
    Validate a spack package installation.

    This endpoint executes singularity-based validation commands to test package functionality.

    Args:
        request: Package validation parameters

    Returns:
        Package validation result with status and details.
    """
    try:
        result = await spack.validate_package(
            package_name=request.package_name,
            package_type=request.package_type,
            installation_digest=request.installation_digest,
            custom_validation_script=request.custom_validation_script,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        logger.exception("Failed to validate package", package=request.package_name, error=str(e))
        return SpackValidationResult(
            success=False,
            message=f"Package validation failed: {str(e)}",
            package_name=request.package_name,
            package_type=request.package_type,
            validation_command="",
            validation_details={"error": str(e)},
        )


@router.post("/validate/stream", operation_id="validate_package_stream")
async def validate_package_stream(
    request: SpackValidateRequest, spack: SpackService = Depends(get_spack_service)
) -> StreamingResponse:
    """
    Validate a spack package installation with streaming output.

    This endpoint executes singularity-based validation commands to test package functionality
    and streams the results in real-time.

    Args:
        request: Package validation parameters

    Returns:
        Streaming validation results
    """
    try:
        from ..models.responses import SpackValidationStreamResult

        async def generate_stream():
            async for result in spack.validate_package_stream(
                package_name=request.package_name,
                package_type=request.package_type,
                installation_digest=request.installation_digest,
                custom_validation_script=request.custom_validation_script,
                session_id=request.session_id,
            ):
                yield f"data: {result.model_dump_json()}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    except Exception as e:
        logger.exception("Failed to validate package with streaming", package=request.package_name, error=str(e))
        # Return error as a single stream event
        error_result = SpackValidationStreamResult(
            type="error",
            data=f"Validation failed: {str(e)}",
            timestamp=time.time(),
            package_name=request.package_name,
            package_type=request.package_type,
        )

        async def generate_error_stream():
            yield f"data: {error_result.model_dump_json()}\n\n"

        return StreamingResponse(
            generate_error_stream(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )


@router.post("/uninstall-all", response_model=SpackUninstallAllResult, operation_id="uninstall_package_with_dependents")
async def uninstall_package_with_dependents(
    request: SpackUninstallAllRequest, spack: SpackService = Depends(get_spack_service)
) -> SpackUninstallAllResult:
    """
    Uninstall a spack package and all its dependents.

    This endpoint executes: spack uninstall -y --all --dependents {package_name}

    Args:
        request: Package uninstall parameters

    Returns:
        Uninstall result with status and details.
    """
    try:
        result = await spack.uninstall_package_with_dependents(
            package_name=request.package_name,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        logger.exception("Failed to uninstall package with dependents", package=request.package_name, error=str(e))
        return SpackUninstallAllResult(
            success=False,
            message=f"Failed to uninstall package with dependents: {str(e)}",
            package_name=request.package_name,
            uninstalled_packages=[],
            uninstall_details={"error": str(e)},
        )
