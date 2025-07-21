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
        Run a git command asynchronously with secure GitHub credentials.

        Args:
            command: Command and arguments to run
            cwd: Working directory
            timeout: Command timeout in seconds

        Returns:
            Command execution result
        """
        import asyncio
        import os
        import shutil
        import tempfile

        logger.debug("Running git command", command=" ".join(command), cwd=str(cwd))

        # Set up secure GitHub credentials
        original_env = os.environ.copy()
        temp_credentials_dir = None

        try:
            # Create temporary directory for git credentials
            temp_credentials_dir = tempfile.mkdtemp(prefix="git-credentials-")

            # Copy secure GitHub token to temporary location
            secure_token_path = Path("/opt/git-credentials/github-token")
            if secure_token_path.exists():
                temp_credentials_path = Path(temp_credentials_dir) / ".git-credentials"
                shutil.copy2(secure_token_path, temp_credentials_path)
                os.chmod(temp_credentials_path, 0o600)

                # Set up git configuration to use the secure credentials
                git_config_path = Path(temp_credentials_dir) / "gitconfig"
                git_config_content = """[credential]
    helper = store
[user]
    name = mercury
    email = mercury@sanger.ac.uk
"""
                git_config_path.write_text(git_config_content)

                # Set environment variables for git to use our secure credentials
                env = os.environ.copy()
                env["HOME"] = temp_credentials_dir
                env["GIT_CONFIG_GLOBAL"] = str(git_config_path)
            else:
                # Fallback to original environment if secure token not found
                env = original_env
                logger.warning("Secure GitHub token not found, using default credentials")

            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                env=env,
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
        finally:
            # Clean up temporary credentials directory
            if temp_credentials_dir and os.path.exists(temp_credentials_dir):
                shutil.rmtree(temp_credentials_dir, ignore_errors=True)

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
        package_name: str | None = None,
    ) -> GitCommitInfoResult:
        """
        Get git commit information for a repository and update the session recipe.
        """
        logger.info("Getting git commit info", repo_url=repo_url, session_id=session_id, package_name=package_name)

        if not package_name:
            return GitCommitInfoResult(
                success=False,
                message="Package name is required",
                commit_hash="",
                commit_date="",
                repo_url=repo_url,
            )

        try:
            # Create session-specific directory for cloning
            if not session_id:
                return GitCommitInfoResult(
                    success=False,
                    message="Session ID is required",
                    commit_hash="",
                    commit_date="",
                    repo_url=repo_url,
                )

            session_dir = Path(f"/tmp/{session_id}")
            clone_dir = session_dir / "git-clone-temp"

            # Clean up existing directory
            if clone_dir.exists():
                shutil.rmtree(clone_dir)

            # Clone repository
            clone_cmd = ["git", "clone", repo_url, str(clone_dir)]
            clone_result = await self._run_command(clone_cmd, timeout=300)

            if not clone_result["success"]:
                return GitCommitInfoResult(
                    success=False,
                    message=f"Failed to clone repository: {clone_result['stderr']}",
                    commit_hash="",
                    commit_date="",
                    repo_url=repo_url,
                )

            # Get commit information
            commit_cmd = ["git", "log", "-1", "--format=%H"]
            commit_result = await self._run_command(commit_cmd, cwd=clone_dir)

            if not commit_result["success"]:
                return GitCommitInfoResult(
                    success=False,
                    message=f"Failed to get commit hash: {commit_result['stderr']}",
                    commit_hash="",
                    commit_date="",
                    repo_url=repo_url,
                )

            commit_hash = commit_result["stdout"].strip()

            # Get commit date
            date_cmd = ["git", "log", "-1", "--format=%cd", "--date=format:%Y%m%d"]
            date_result = await self._run_command(date_cmd, cwd=clone_dir)

            if not date_result["success"]:
                return GitCommitInfoResult(
                    success=False,
                    message=f"Failed to get commit date: {date_result['stderr']}",
                    commit_hash="",
                    commit_date="",
                    repo_url=repo_url,
                )

            commit_date = date_result["stdout"].strip()

            # Clean up clone directory
            shutil.rmtree(clone_dir)

            # Create blank recipe if it doesn't exist
            recipe_path = session_dir / "spack-repo" / "packages" / package_name / "package.py"

            if not recipe_path.exists():
                # Import here to avoid circular imports
                from ..services.spack_service import get_spack_service

                spack_service = get_spack_service()

                # Run spack create to generate blank template
                create_cmd = [str(spack_service.spack_cmd), "create", "--skip-editor", package_name]
                create_result = await spack_service._run_spack_command(create_cmd, session_id=session_id, timeout=120)

                if not create_result["success"]:
                    return GitCommitInfoResult(
                        success=False,
                        message=f"Failed to create blank recipe: {create_result['stderr']}",
                        commit_hash=commit_hash,
                        commit_date=commit_date,
                        repo_url=repo_url,
                    )

            # Read the recipe file
            if not recipe_path.exists():
                return GitCommitInfoResult(
                    success=False,
                    message="Recipe file was not created",
                    commit_hash=commit_hash,
                    commit_date=commit_date,
                    repo_url=repo_url,
                )

            with open(recipe_path) as f:
                lines = f.readlines()

            # Replace homepage line with the git URL if it exists, and ensure git line is present after homepage
            homepage_replaced = False
            insert_idx = None
            lines_to_remove = []

            for i, line in enumerate(lines):
                if "homepage" in line and "=" in line:
                    lines[i] = f'    homepage = "{repo_url}"\n'
                    homepage_replaced = True
                    insert_idx = i + 1
                # Remove any url line
                if line.strip().startswith("url ="):
                    lines[i] = None
                # Remove FIXME maintainers comment block
                if "# FIXME: Add a list of GitHub accounts to" in line:
                    lines_to_remove.extend([i, i + 1, i + 2])  # Remove this line and next 2 lines
                # Remove FIXME versions comment block
                if "# FIXME: Add proper versions here." in line:
                    lines_to_remove.extend([i, i + 1])  # Remove this line and next line

            # Remove lines in reverse order to maintain indices
            for idx in sorted(lines_to_remove, reverse=True):
                if idx < len(lines):
                    lines[idx] = None

            # Remove all None lines (url lines and FIXME blocks)
            lines = [line for line in lines if line is not None]

            if homepage_replaced:
                # Insert git after homepage
                lines.insert(insert_idx, f'    git = "{repo_url}"\n')
                insert_idx += 1
            else:
                # If no homepage found, insert after the class definition
                for i, line in enumerate(lines):
                    if line.strip().startswith("class ") and ":" in line:
                        insert_idx = i + 1
                        break
                if insert_idx is None:
                    insert_idx = 1  # Default to after the first line
                lines.insert(insert_idx, f'    homepage = "{repo_url}"\n')
                insert_idx += 1
                lines.insert(insert_idx, f'    git = "{repo_url}"\n')
                insert_idx += 1

            # Insert version line after git
            version_line = f'    version("{commit_date}", commit="{commit_hash}")\n'
            lines.insert(insert_idx, version_line)

            # Write the updated recipe back
            with open(recipe_path, "w") as f:
                f.writelines(lines)

            logger.success(
                "Updated recipe with git info",
                session_id=session_id,
                package_name=package_name,
                commit_hash=commit_hash,
                commit_date=commit_date,
            )

            return GitCommitInfoResult(
                success=True,
                message="Successfully updated recipe with git commit info",
                commit_hash=commit_hash,
                commit_date=commit_date,
                repo_url=repo_url,
            )

        except Exception as e:
            logger.exception("Failed to get git commit info", repo_url=repo_url, error=str(e))
            return GitCommitInfoResult(
                success=False,
                message=f"Failed to get git commit info: {str(e)}",
                commit_hash="",
                commit_date="",
                repo_url=repo_url,
            )

    async def create_pull_request(
        self,
        package_name: str,
        recipe_name: str | None = None,
        session_id: str | None = None,
    ) -> GitPullRequestResult:
        """
        Create a pull request for a package recipe.

        This method:
        1. Clones the spack-repo repository to a fresh location
        2. Creates a new branch
        3. Copies all changes from the session packages directory
        4. Commits and pushes the changes
        5. Returns the GitHub PR creation URL

        Args:
            package_name: Package name
            recipe_name: Recipe name (defaults to package_name)
            session_id: Optional session ID for isolated execution

        Returns:
            Pull request creation result with GitHub PR URL
        """
        if recipe_name is None:
            recipe_name = package_name

        logger.info("Creating pull request", package=package_name, recipe=recipe_name, session_id=session_id)

        try:
            # Determine session directory
            session_dir = None
            if session_id:
                session_manager = get_session_manager()
                session_dir = session_manager.get_session_dir(session_id)

            if not session_dir or not session_dir.exists():
                return GitPullRequestResult(
                    success=False,
                    message="Session directory not found or not initialized",
                    package_name=package_name,
                    pr_details={"error": "Session directory not found"},
                )

            # Create fresh clone directory
            import time
            import uuid

            clone_uuid = str(uuid.uuid4())
            clone_dir = Path(f"/tmp/{clone_uuid}")
            spack_repo_url = "https://github.com/wtsi-hgi/spack-repo.git"

            # Create unique branch name with timestamp to avoid conflicts
            timestamp = int(time.time())
            branch_name = f"add-{package_name}-recipe-{timestamp}"
            commit_message = f"Add {recipe_name} recipe"

            executed_commands = []

            # Step 1: Clone the repository
            logger.info("Cloning spack-repo", clone_dir=clone_dir)
            clone_cmd = ["git", "clone", spack_repo_url, str(clone_dir)]
            clone_result = await self._run_command(clone_cmd, timeout=300)
            executed_commands.append(" ".join(clone_cmd))

            if not clone_result["success"]:
                logger.error("Git clone failed", error=clone_result["stderr"])
                return GitPullRequestResult(
                    success=False,
                    message=f"Failed to clone repository: {clone_result['stderr']}",
                    package_name=package_name,
                    git_commands=executed_commands,
                    pr_details={
                        "failed_command": " ".join(clone_cmd),
                        "error": clone_result["stderr"],
                        "stdout": clone_result["stdout"],
                    },
                )

            # Step 2: Create new branch
            logger.info("Creating new branch", branch=branch_name)
            checkout_cmd = ["git", "checkout", "-b", branch_name]
            checkout_result = await self._run_command(checkout_cmd, cwd=clone_dir, timeout=60)
            executed_commands.append(" ".join(checkout_cmd))

            if not checkout_result["success"]:
                logger.error("Branch creation failed", error=checkout_result["stderr"])
                # Clean up clone directory
                if clone_dir.exists():
                    shutil.rmtree(clone_dir)

                # Check if it's a branch already exists error
                if "already exists" in checkout_result["stderr"]:
                    return GitPullRequestResult(
                        success=False,
                        message=(
                            f"Branch {branch_name} already exists. " "Please try again or use a different package name."
                        ),
                        package_name=package_name,
                        branch_name=branch_name,
                        git_commands=executed_commands,
                        pr_details={
                            "failed_command": " ".join(checkout_cmd),
                            "error": checkout_result["stderr"],
                            "stdout": checkout_result["stdout"],
                            "suggestion": "Try again in a few seconds or use a different package name",
                        },
                    )

                return GitPullRequestResult(
                    success=False,
                    message=f"Failed to create branch: {checkout_result['stderr']}",
                    package_name=package_name,
                    branch_name=branch_name,
                    git_commands=executed_commands,
                    pr_details={
                        "failed_command": " ".join(checkout_cmd),
                        "error": checkout_result["stderr"],
                        "stdout": checkout_result["stdout"],
                    },
                )

            # Step 3: Copy changes from session packages directory
            session_packages_dir = session_dir / "spack-repo" / "packages"
            if session_packages_dir.exists():
                logger.info("Copying package changes", source=session_packages_dir, dest=clone_dir / "packages")

                # Copy all packages from session to fresh clone
                for package_dir in session_packages_dir.iterdir():
                    if package_dir.is_dir():
                        dest_package_dir = clone_dir / "packages" / package_dir.name

                        # Remove existing directory if it exists
                        if dest_package_dir.exists():
                            shutil.rmtree(dest_package_dir)

                        # Copy the entire package directory
                        shutil.copytree(package_dir, dest_package_dir)
                        logger.info("Copied package", package=package_dir.name)

                # Add copy command to executed commands for UI display
                executed_commands.append(f"cp -r {session_packages_dir}/* {clone_dir}/packages/")

            # Step 4: Add all changes
            add_cmd = ["git", "add", "."]
            add_result = await self._run_command(add_cmd, cwd=clone_dir, timeout=60)
            executed_commands.append(" ".join(add_cmd))

            if not add_result["success"]:
                logger.error("Git add failed", error=add_result["stderr"])
                # Clean up clone directory
                if clone_dir.exists():
                    shutil.rmtree(clone_dir)
                return GitPullRequestResult(
                    success=False,
                    message=f"Failed to add changes: {add_result['stderr']}",
                    package_name=package_name,
                    branch_name=branch_name,
                    git_commands=executed_commands,
                    pr_details={
                        "failed_command": " ".join(add_cmd),
                        "error": add_result["stderr"],
                        "stdout": add_result["stdout"],
                    },
                )

            # Check if there are any changes to commit
            status_cmd = ["git", "status", "--porcelain"]
            status_result = await self._run_command(status_cmd, cwd=clone_dir, timeout=30)
            if status_result["success"] and not status_result["stdout"].strip():
                logger.warning("No changes to commit", package=package_name)
                return GitPullRequestResult(
                    success=False,
                    message=(
                        "No changes to commit. The package files may not have been copied correctly "
                        "or there are no differences from the base repository."
                    ),
                    package_name=package_name,
                    branch_name=branch_name,
                    git_commands=executed_commands,
                    pr_details={
                        "error": "No changes detected",
                        "status_output": status_result["stdout"],
                        "suggestion": "Check if the package files were copied correctly from the session",
                    },
                )

            # Step 5: Commit changes
            commit_cmd = ["git", "commit", "-m", commit_message]
            commit_result = await self._run_command(commit_cmd, cwd=clone_dir, timeout=60)
            # Display the command with proper quoting for the UI
            executed_commands.append(f'git commit -m "{commit_message}"')

            if not commit_result["success"]:
                logger.error("Git commit failed", error=commit_result["stderr"], stdout=commit_result["stdout"])
                # Clean up clone directory
                if clone_dir.exists():
                    shutil.rmtree(clone_dir)
                return GitPullRequestResult(
                    success=False,
                    message=f"Failed to commit changes: {commit_result['stderr']}",
                    package_name=package_name,
                    branch_name=branch_name,
                    commit_message=commit_message,
                    git_commands=executed_commands,
                    pr_details={
                        "failed_command": " ".join(commit_cmd),
                        "error": commit_result["stderr"],
                        "stdout": commit_result["stdout"],
                    },
                )

            # Step 6: Push branch
            push_cmd = ["git", "push", "origin", branch_name]
            push_result = await self._run_command(push_cmd, cwd=clone_dir, timeout=120)
            executed_commands.append(" ".join(push_cmd))

            if not push_result["success"]:
                logger.error("Git push failed", error=push_result["stderr"])
                # Clean up clone directory
                if clone_dir.exists():
                    shutil.rmtree(clone_dir)

                # Check for specific push errors
                error_msg = push_result["stderr"]
                if "non-fast-forward" in error_msg or "rejected" in error_msg:
                    return GitPullRequestResult(
                        success=False,
                        message=(
                            f"Branch {branch_name} already exists on remote. "
                            "This usually means the branch was created in a previous attempt. "
                            "Please try again with a different package name or wait a few minutes."
                        ),
                        package_name=package_name,
                        branch_name=branch_name,
                        commit_message=commit_message,
                        git_commands=executed_commands,
                        pr_details={
                            "failed_command": " ".join(push_cmd),
                            "error": push_result["stderr"],
                            "stdout": push_result["stdout"],
                            "suggestion": "Try again with a different package name or wait a few minutes",
                        },
                    )
                elif "Authentication failed" in error_msg:
                    return GitPullRequestResult(
                        success=False,
                        message="Git authentication failed. Please check your git credentials and try again.",
                        package_name=package_name,
                        branch_name=branch_name,
                        commit_message=commit_message,
                        git_commands=executed_commands,
                        pr_details={
                            "failed_command": " ".join(push_cmd),
                            "error": push_result["stderr"],
                            "stdout": push_result["stdout"],
                            "suggestion": "Check git credentials and authentication",
                        },
                    )

                return GitPullRequestResult(
                    success=False,
                    message=f"Failed to push branch: {push_result['stderr']}",
                    package_name=package_name,
                    branch_name=branch_name,
                    commit_message=commit_message,
                    git_commands=executed_commands,
                    pr_details={
                        "failed_command": " ".join(push_cmd),
                        "error": push_result["stderr"],
                        "stdout": push_result["stdout"],
                    },
                )

            # Step 7: Clean up clone directory
            if clone_dir.exists():
                shutil.rmtree(clone_dir)

            # Step 8: Generate PR URL
            pr_url = f"https://github.com/wtsi-hgi/spack-repo/compare/main...{branch_name}"

            logger.success(
                "Pull request preparation completed", package=package_name, branch=branch_name, pr_url=pr_url
            )
            return GitPullRequestResult(
                success=True,
                message=f"Successfully prepared pull request for {package_name}. Branch {branch_name} has been pushed.",
                package_name=package_name,
                branch_name=branch_name,
                commit_message=commit_message,
                git_commands=executed_commands,
                pr_url=pr_url,
                pr_details={
                    "branch_created": branch_name,
                    "commit_created": commit_message,
                    "clone_uuid": clone_uuid,
                    "next_step": "Click the PR URL to create the pull request on GitHub",
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
