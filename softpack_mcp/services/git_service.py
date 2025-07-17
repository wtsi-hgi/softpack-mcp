"""
Git service for managing git operations.
"""

import shutil
from pathlib import Path

from loguru import logger

from ..models.responses import GitCommitInfoResult, GitPullRequestResult, GitPullResult
from .session_manager import get_session_manager


class GitService:
    """Service for interacting with Git repositories."""

    def __init__(self):
        """Initialize Git service."""
        logger.info("Initialized GitService")

    async def _run_command(self, command: list[str], cwd: Path | None = None, timeout: int = 300) -> dict[str, any]:
        """
        Run a git command asynchronously.

        Args:
            command: Command and arguments to run
            cwd: Working directory
            timeout: Command timeout in seconds

        Returns:
            Command execution result
        """
        import asyncio

        logger.debug("Running git command", command=" ".join(command), cwd=str(cwd))

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            result = {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8") if stdout else "",
                "stderr": stderr.decode("utf-8") if stderr else "",
                "success": process.returncode == 0,
            }

            if not result["success"]:
                logger.error(
                    "Git command failed",
                    command=" ".join(command),
                    returncode=process.returncode,
                    stderr=result["stderr"],
                )
            else:
                logger.debug("Git command completed successfully", command=" ".join(command))

            return result

        except asyncio.TimeoutError:
            logger.error("Git command timed out", command=" ".join(command), timeout=timeout)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "success": False,
            }
        except Exception as e:
            logger.exception("Git command execution failed", command=" ".join(command), error=str(e))
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
            }

    async def pull_spack_repo_updates(
        self,
        repo_path: str | None = None,
    ) -> GitPullResult:
        """
        Pull the latest updates from the spack-repo.

        Args:
            repo_path: Path to the spack repository (defaults to ~/spack-repo)

        Returns:
            Git pull result
        """
        if repo_path is None:
            repo_path = str(Path.home() / "spack-repo")

        repo_dir = Path(repo_path)
        logger.info("Pulling spack-repo updates", repo_path=repo_path)

        try:
            if not repo_dir.exists():
                logger.error("Spack repository not found", repo_path=repo_path)
                return GitPullResult(
                    success=False,
                    message=f"Spack repository not found at {repo_path}",
                    repository_path=repo_path,
                    changes_pulled=False,
                    pull_details={"error": "Repository directory not found"},
                )

            # Get current commit hash before pull
            before_commit_cmd = ["git", "rev-parse", "HEAD"]
            before_result = await self._run_command(before_commit_cmd, cwd=repo_dir, timeout=30)
            before_commit = before_result["stdout"].strip() if before_result["success"] else None

            # Pull updates from origin
            pull_cmd = ["git", "pull", "origin", "main"]
            pull_result = await self._run_command(pull_cmd, cwd=repo_dir, timeout=180)

            if not pull_result["success"]:
                logger.error("Git pull failed", repo_path=repo_path, error=pull_result["stderr"])
                return GitPullResult(
                    success=False,
                    message=f"Failed to pull updates: {pull_result['stderr']}",
                    repository_path=repo_path,
                    changes_pulled=False,
                    pull_details={
                        "error": pull_result["stderr"],
                        "stdout": pull_result["stdout"],
                    },
                )

            # Get commit hash after pull
            after_commit_cmd = ["git", "rev-parse", "HEAD"]
            after_result = await self._run_command(after_commit_cmd, cwd=repo_dir, timeout=30)
            after_commit = after_result["stdout"].strip() if after_result["success"] else None

            # Check if there were changes
            changes_pulled = before_commit != after_commit if before_commit and after_commit else True

            # Get number of files changed if there were updates
            files_changed = []
            if changes_pulled and before_commit and after_commit:
                diff_cmd = ["git", "diff", "--name-only", before_commit, after_commit]
                diff_result = await self._run_command(diff_cmd, cwd=repo_dir, timeout=30)
                if diff_result["success"]:
                    files_changed = [f.strip() for f in diff_result["stdout"].split("\n") if f.strip()]

            message = (
                f"Successfully pulled updates. {len(files_changed)} files changed."
                if changes_pulled
                else "Repository is already up to date."
            )

            logger.success(
                "Spack repo updated", repo_path=repo_path, changes=changes_pulled, files_changed=len(files_changed)
            )
            return GitPullResult(
                success=True,
                message=message,
                repository_path=repo_path,
                changes_pulled=changes_pulled,
                commit_hash=after_commit,
                pull_details={
                    "before_commit": before_commit,
                    "after_commit": after_commit,
                    "files_changed": files_changed,
                    "pull_output": pull_result["stdout"],
                },
            )

        except Exception as e:
            logger.exception("Git pull failed", repo_path=repo_path, error=str(e))
            return GitPullResult(
                success=False,
                message=f"Failed to pull spack-repo updates: {str(e)}",
                repository_path=repo_path,
                changes_pulled=False,
                pull_details={"error": str(e)},
            )

    async def get_commit_info(
        self,
        repo_url: str,
        session_id: str | None = None,
    ) -> GitCommitInfoResult:
        """
        Get git commit information for a repository.

        Args:
            repo_url: Repository URL
            session_id: Optional session ID for context

        Returns:
            Git commit information result
        """
        logger.info("Getting git commit info", repo_url=repo_url, session_id=session_id)

        try:
            # Create temporary directory for cloning
            clone_dir = Path("/tmp/scratch")

            # Clean up existing directory
            if clone_dir.exists():
                shutil.rmtree(clone_dir)

            # Clone repository
            clone_cmd = ["git", "clone", repo_url, str(clone_dir)]
            clone_result = await self._run_command(clone_cmd, timeout=300)

            if not clone_result["success"]:
                logger.error("Git clone failed", repo_url=repo_url, error=clone_result["stderr"])
                return GitCommitInfoResult(
                    success=False,
                    message=f"Failed to clone repository {repo_url}: {clone_result['stderr']}",
                    repo_url=repo_url,
                    commit_details={"error": clone_result["stderr"]},
                )

            # Get commit hash
            commit_cmd = ["git", "log", "-1", "--format=%H"]
            commit_result = await self._run_command(commit_cmd, cwd=clone_dir, timeout=30)

            # Get commit date
            date_cmd = ["git", "log", "-1", "--format=%cd", "--date=format:%Y%m%d"]
            date_result = await self._run_command(date_cmd, cwd=clone_dir, timeout=30)

            # Clean up
            if clone_dir.exists():
                shutil.rmtree(clone_dir)

            if not commit_result["success"] or not date_result["success"]:
                logger.error("Failed to get commit info", repo_url=repo_url)
                return GitCommitInfoResult(
                    success=False,
                    message=f"Failed to get commit information from {repo_url}",
                    repo_url=repo_url,
                    commit_details={"commit_error": commit_result["stderr"], "date_error": date_result["stderr"]},
                )

            commit_hash = commit_result["stdout"].strip()
            commit_date = date_result["stdout"].strip()

            logger.success("Retrieved git commit info", repo_url=repo_url, commit=commit_hash[:8])
            return GitCommitInfoResult(
                success=True,
                message=f"Retrieved commit information for {repo_url}",
                repo_url=repo_url,
                commit_hash=commit_hash,
                commit_date=commit_date,
                commit_details={
                    "full_commit_hash": commit_hash,
                    "commit_date": commit_date,
                    "clone_output": clone_result["stdout"],
                },
            )

        except Exception as e:
            logger.exception("Git commit info failed", repo_url=repo_url, error=str(e))
            return GitCommitInfoResult(
                success=False,
                message=f"Failed to get git commit info: {str(e)}",
                repo_url=repo_url,
                commit_details={"error": str(e)},
            )

    async def create_pull_request(
        self,
        package_name: str,
        recipe_name: str | None = None,
        session_id: str | None = None,
    ) -> GitPullRequestResult:
        """
        Create a pull request for a package recipe.

        Args:
            package_name: Package name
            recipe_name: Recipe name (defaults to package_name)
            session_id: Optional session ID for isolated execution

        Returns:
            Pull request creation result
        """
        if recipe_name is None:
            recipe_name = package_name

        logger.info("Creating pull request", package=package_name, recipe=recipe_name, session_id=session_id)

        try:
            # Determine working directory
            working_dir = None
            if session_id:
                session_manager = get_session_manager()
                session_dir = session_manager.get_session_dir(session_id)
                if session_dir:
                    working_dir = session_dir / "spack-repo"

            if not working_dir or not working_dir.exists():
                return GitPullRequestResult(
                    success=False,
                    message="Session directory not found or not initialized",
                    package_name=package_name,
                    pr_details={"error": "Working directory not found"},
                )

            # Git commands to execute
            branch_name = f"add-{package_name}-recipe"
            commit_message = f"Add {recipe_name} recipe"

            git_commands = [
                ["git", "checkout", "-b", branch_name],
                ["git", "add", "."],
                ["git", "commit", "-m", commit_message],
                ["git", "push", "origin", branch_name],
            ]

            executed_commands = []
            for cmd in git_commands:
                result = await self._run_command(cmd, cwd=working_dir, timeout=60)
                executed_commands.append(" ".join(cmd))

                if not result["success"]:
                    logger.error("Git command failed", command=" ".join(cmd), error=result["stderr"])
                    return GitPullRequestResult(
                        success=False,
                        message=f"Git command failed: {' '.join(cmd)} - {result['stderr']}",
                        package_name=package_name,
                        branch_name=branch_name,
                        commit_message=commit_message,
                        git_commands=executed_commands,
                        pr_details={
                            "failed_command": " ".join(cmd),
                            "error": result["stderr"],
                            "stdout": result["stdout"],
                        },
                    )

            logger.success("Pull request preparation completed", package=package_name, branch=branch_name)
            return GitPullRequestResult(
                success=True,
                message=f"Successfully prepared pull request for {package_name}. Branch {branch_name} has been pushed.",
                package_name=package_name,
                branch_name=branch_name,
                commit_message=commit_message,
                git_commands=executed_commands,
                pr_details={
                    "branch_created": branch_name,
                    "commit_created": commit_message,
                    "next_step": "Create PR on GitHub web interface",
                },
            )

        except Exception as e:
            logger.exception("Pull request creation failed", package=package_name, error=str(e))
            return GitPullRequestResult(
                success=False,
                message=f"Failed to create pull request: {str(e)}",
                package_name=package_name,
                pr_details={"error": str(e)},
            )


# Global service instance
_git_service: GitService | None = None


def get_git_service() -> GitService:
    """Get the global git service instance."""
    global _git_service
    if _git_service is None:
        _git_service = GitService()
    return _git_service
