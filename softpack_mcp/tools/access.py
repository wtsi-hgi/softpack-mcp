"""
Access MCP tools.
"""

from fastapi import APIRouter, Depends
from loguru import logger

from ..models.requests import AccessRequestRequest
from ..models.responses import AccessRequestResult
from ..services.access_service import AccessService, get_access_service

router = APIRouter()


@router.post("/request", response_model=AccessRequestResult, operation_id="request_collaborator_access")
async def request_collaborator_access(
    request: AccessRequestRequest, access_service: AccessService = Depends(get_access_service)
) -> AccessRequestResult:
    """
    Request collaborator access to spack-repo.

    This endpoint sends an email to the HGI service desk requesting
    collaborator access for the specified GitHub username.

    Args:
        request: Access request parameters

    Returns:
        Access request result with status and details.
    """
    try:
        result = await access_service.request_collaborator_access(request)
        return result
    except Exception as e:
        logger.exception(
            "Failed to request collaborator access",
            github_username=request.github_username,
            package_name=request.package_name,
            error=str(e),
        )
        return AccessRequestResult(
            success=False,
            message=f"Failed to request collaborator access: {str(e)}",
            github_username=request.github_username,
            package_name=request.package_name,
            email_sent=False,
            email_details={"error": str(e)},
        )
