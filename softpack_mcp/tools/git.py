"""
Git MCP tools.
"""

from pathlib import Path

from fastapi import APIRouter, Depends
from loguru import logger

from ..models.requests import GitCommitInfoRequest, GitPullRequest, GitPullRequestRequest
from ..models.responses import GitCommitInfoResult, GitPullRequestResult, GitPullResult
from ..services.git_service import GitService, get_git_service

router = APIRouter()


@router.post("/pull", response_model=GitPullResult, operation_id="pull_spack_repo")
async def pull_spack_repo(request: GitPullRequest, git_service: GitService = Depends(get_git_service)) -> GitPullResult:
    """
    Pull the latest updates from the spack-repo.

    This endpoint pulls the latest changes from the spack-repo to ensure
    that sessions work with the most up-to-date package definitions.

    Args:
        request: Git pull request parameters

    Returns:
        Git pull result with status and details.
    """
    try:
        result = await git_service.pull_spack_repo_updates(
            repo_path=request.repo_path,
        )
        return result
    except Exception as e:
        logger.exception("Failed to pull spack-repo updates", error=str(e))
        return GitPullResult(
            success=False,
            message=f"Failed to pull spack-repo updates: {str(e)}",
            repository_path=request.repo_path or str(Path.home() / "spack-repo"),
            changes_pulled=False,
            pull_details={"error": str(e)},
        )


@router.post("/commit-info", response_model=GitCommitInfoResult, operation_id="get_git_commit_info")
async def get_git_commit_info(
    request: GitCommitInfoRequest, git_service: GitService = Depends(get_git_service)
) -> GitCommitInfoResult:
    """
    Get git commit information for a repository and update the session recipe.
    """
    try:
        result = await git_service.get_commit_info(
            repo_url=request.repo_url,
            session_id=request.session_id,
            package_name=request.package_name,
        )
        return result
    except Exception as e:
        logger.exception("Failed to get git commit info", repo_url=request.repo_url, error=str(e))
        return GitCommitInfoResult(
            success=False,
            message=f"Failed to get git commit info: {str(e)}",
            repo_url=request.repo_url,
            commit_details={"error": str(e)},
        )


@router.post("/pull-request", response_model=GitPullRequestResult, operation_id="create_pull_request")
async def create_pull_request(
    request: GitPullRequestRequest, git_service: GitService = Depends(get_git_service)
) -> GitPullRequestResult:
    """
    Create a pull request for a package recipe.

    This endpoint executes git commands to create a branch, commit changes, and push.
    Used in the final step of the spack package creation workflow.

    Args:
        request: Pull request creation parameters

    Returns:
        Pull request creation result with status and details.
    """
    try:
        result = await git_service.create_pull_request(
            package_name=request.package_name,
            recipe_name=request.recipe_name,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        logger.exception("Failed to create pull request", package=request.package_name, error=str(e))
        return GitPullRequestResult(
            success=False,
            message=f"Failed to create pull request: {str(e)}",
            package_name=request.package_name,
            pr_details={"error": str(e)},
        )
