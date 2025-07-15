"""
Spack service for managing spack operations.
"""

import asyncio
import re
import shutil
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from loguru import logger

from ..config import get_settings
from ..models.responses import (
    OperationResult,
    SpackCopyPackageResult,
    SpackCreatePypiResult,
    SpackInstallStreamResult,
    SpackPackage,
    SpackVariant,
    SpackVersionInfo,
)
from .session_manager import get_session_manager


class SpackService:
    """Service for interacting with Spack package manager."""

    def __init__(self, spack_executable: str | None = None):
        """
        Initialize Spack service.

        Args:
            spack_executable: Path to spack executable
        """
        if spack_executable is None:
            settings = get_settings()
            spack_executable = settings.spack_executable

        self.spack_cmd = Path(spack_executable)
        logger.info("Initialized SpackService", spack_executable=str(self.spack_cmd))

    async def _run_command_base(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout: int = 300,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Base method for running shell commands asynchronously.

        Args:
            command: Command and arguments to run
            cwd: Working directory
            timeout: Command timeout in seconds
            session_id: Optional session ID for isolated execution

        Returns:
            Command execution result
        """
        logger.debug("Running command", command=" ".join(command), cwd=str(cwd), session_id=session_id)

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
                    "Command failed",
                    command=" ".join(command),
                    returncode=process.returncode,
                    stderr=result["stderr"],
                )
            else:
                logger.debug("Command completed successfully", command=" ".join(command))

            return result

        except asyncio.TimeoutError:
            logger.error("Command timed out", command=" ".join(command), timeout=timeout)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "success": False,
            }
        except Exception as e:
            logger.exception("Command execution failed", command=" ".join(command), error=str(e))
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
            }

    async def _run_command(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """
        Run a general shell command asynchronously (without spack session handling).

        Args:
            command: Command and arguments to run
            cwd: Working directory
            timeout: Command timeout in seconds

        Returns:
            Command execution result
        """
        return await self._run_command_base(command, cwd=cwd, timeout=timeout)

    async def _run_spack_command(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout: int = 300,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Run a spack command asynchronously with session isolation support.

        Args:
            command: Command and arguments to run
            cwd: Working directory
            timeout: Command timeout in seconds
            session_id: Optional session ID for isolated execution

        Returns:
            Command execution result
        """
        # Handle session-based execution with singularity
        if session_id:
            session_manager = get_session_manager()
            try:
                singularity_prefix = session_manager.get_singularity_command_prefix(session_id)
                if command[0] == str(self.spack_cmd):
                    command = singularity_prefix + command[1:]
                else:
                    command = singularity_prefix + command
            except ValueError as e:
                logger.error("Failed to get session singularity prefix", session_id=session_id, error=str(e))
                raise

        return await self._run_command_base(command, cwd=cwd, timeout=timeout, session_id=session_id)

    async def search_packages(
        self,
        query: str = "",
        limit: int = 50,
        session_id: str | None = None,
    ) -> list[SpackPackage]:
        """
        Search for spack packages.

        Args:
            query: Search query
            limit: Maximum number of packages
            session_id: Optional session ID for isolated execution

        Returns:
            List of spack packages
        """
        logger.info("Searching packages", query=query, limit=limit, session_id=session_id)

        cmd = [str(self.spack_cmd), "list"]
        if query:
            cmd.append(query)

        result = await self._run_spack_command(cmd, session_id=session_id)

        if not result["success"]:
            logger.error("Package search failed", error=result["stderr"])
            return []

        packages = []
        lines = result["stdout"].strip().split("\n")

        for line in lines[:limit]:
            line = line.strip()
            if line and not line.startswith("="):
                packages.append(
                    SpackPackage(
                        name=line,
                        version="latest",
                        description=f"Spack package: {line}",
                        homepage=None,
                        variants=[],
                        dependencies=[],
                        build_dependencies=[],
                        link_dependencies=[],
                        run_dependencies=[],
                        licenses=[],
                    )
                )

        logger.info("Found packages", count=len(packages))
        return packages

    async def install_package(
        self,
        package_name: str,
        version: str | None = None,
        variants: list[str] | None = None,
        dependencies: list[str] | None = None,
        session_id: str | None = None,
    ) -> OperationResult:
        """
        Install a spack package.

        Args:
            package_name: Package name
            version: Package version
            variants: Package variants
            dependencies: Additional dependencies
            session_id: Optional session ID for isolated execution

        Returns:
            Installation result
        """
        spec = package_name
        if version:
            spec += f"@{version}"

        if variants:
            for variant in variants:
                spec += f" {variant}"

        logger.info("Installing package", package=spec, session_id=session_id)

        cmd = [str(self.spack_cmd), "install", spec]

        result = await self._run_spack_command(cmd, timeout=43200, session_id=session_id)  # 12 hours timeout

        if result["success"]:
            logger.success("Package installed successfully", package=spec)
            message = f"Successfully installed {spec}"
        else:
            logger.error("Package installation failed", package=spec, error=result["stderr"])
            message = f"Failed to install {spec}: {result['stderr']}"

        return OperationResult(
            success=result["success"],
            message=message,
            details={
                "package": spec,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
            },
        )

    async def install_package_stream(
        self,
        package_name: str,
        version: str | None = None,
        variants: list[str] | None = None,
        dependencies: list[str] | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[SpackInstallStreamResult, None]:
        """
        Install a spack package with streaming output.

        Args:
            package_name: Package name
            version: Package version
            variants: Package variants
            dependencies: Additional dependencies
            session_id: Optional session ID for isolated execution

        Yields:
            Streaming installation results
        """
        spec = package_name
        if version:
            spec += f"@{version}"

        if variants:
            for variant in variants:
                spec += f" {variant}"

        logger.info("Starting streaming installation", package=spec, session_id=session_id)

        # Send initial status
        yield SpackInstallStreamResult(
            type="start",
            data=f"Starting installation of {spec}" + (f" (session: {session_id})" if session_id else ""),
            timestamp=time.time(),
            package_name=package_name,
            version=version,
        )

        # Build command with session support
        if session_id:
            session_manager = get_session_manager()
            try:
                singularity_prefix = session_manager.get_singularity_command_prefix(session_id)
                cmd = singularity_prefix + ["install", spec]
            except ValueError as e:
                logger.error("Failed to get session singularity prefix", session_id=session_id, error=str(e))
                yield SpackInstallStreamResult(
                    type="error",
                    data=f"Session error: {str(e)}",
                    timestamp=time.time(),
                    package_name=package_name,
                    version=version,
                )
                return
        else:
            cmd = [str(self.spack_cmd), "install", spec]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Create a queue to collect output from both streams
            output_queue = asyncio.Queue()

            # Function to read from a stream and put results in queue
            async def read_stream(stream: asyncio.StreamReader, stream_type: str):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    await output_queue.put(
                        SpackInstallStreamResult(
                            type=stream_type,
                            data=line.decode("utf-8").rstrip(),
                            timestamp=time.time(),
                            package_name=package_name,
                            version=version,
                        )
                    )

            # Start reading both streams concurrently
            stdout_task = asyncio.create_task(read_stream(process.stdout, "output"))
            stderr_task = asyncio.create_task(read_stream(process.stderr, "error"))

            # Yield output as it becomes available
            while True:
                try:
                    # Wait for output with a timeout
                    result = await asyncio.wait_for(output_queue.get(), timeout=0.1)
                    yield result
                except asyncio.TimeoutError:
                    # Check if both streams are done
                    if stdout_task.done() and stderr_task.done():
                        break

            # Wait for process to complete
            returncode = await process.wait()

            # Send completion status
            success = returncode == 0
            if success:
                logger.success("Package installed successfully", package=spec)
                message = f"Successfully installed {spec}"
            else:
                logger.error("Package installation failed", package=spec, returncode=returncode)
                message = f"Failed to install {spec} (return code: {returncode})"

            yield SpackInstallStreamResult(
                type="complete",
                data=message,
                timestamp=time.time(),
                package_name=package_name,
                version=version,
                success=success,
            )

        except Exception as e:
            logger.exception("Streaming installation failed", package=spec, error=str(e))
            yield SpackInstallStreamResult(
                type="error",
                data=f"Installation failed: {str(e)}",
                timestamp=time.time(),
                package_name=package_name,
                version=version,
            )

    async def uninstall_package(
        self,
        package_name: str,
        version: str | None = None,
        force: bool = False,
        session_id: str | None = None,
    ) -> bool:
        """
        Uninstall a spack package.

        Args:
            package_name: Package name
            version: Package version
            force: Force uninstallation
            session_id: Optional session ID for isolated execution

        Returns:
            True if successful
        """
        spec = package_name
        if version:
            spec += f"@{version}"

        logger.info("Uninstalling package", package=spec, force=force, session_id=session_id)

        cmd = [str(self.spack_cmd), "uninstall"]
        if force:
            cmd.append("--force")
        cmd.append(spec)

        result = await self._run_spack_command(cmd, session_id=session_id)

        if result["success"]:
            logger.success("Package uninstalled successfully", package=spec)
        else:
            logger.error("Package uninstallation failed", package=spec, error=result["stderr"])

        return result["success"]

    async def create_pypi_package(
        self,
        package_name: str,
        session_id: str | None = None,
    ) -> SpackCreatePypiResult:
        """
        Create a PyPI package using PyPackageCreator.

        Args:
            package_name: Name of the PyPI package to create
            session_id: Optional session ID for isolated execution

        Returns:
            Creation result with details
        """
        logger.info("Creating PyPI package", package=package_name, session_id=session_id)

        try:
            # Step 1: Change directory to ~/r-spack-recipe-builder and run PyPackageCreator
            creator_dir = Path.home() / "r-spack-recipe-builder"
            creator_script = creator_dir / "PyPackageCreator.py"

            if not creator_script.exists():
                logger.error("PyPackageCreator.py not found", path=str(creator_script))
                return SpackCreatePypiResult(
                    success=False,
                    message=f"PyPackageCreator.py not found at {creator_script}",
                    package_name=package_name,
                    creation_details={"error": "PyPackageCreator script not found"},
                )

            # Run PyPackageCreator.py with the package name
            cmd = ["uv", "run", str(creator_script), "-f", package_name]
            result = await self._run_command(cmd, cwd=creator_dir, timeout=300)

            if not result["success"]:
                logger.error("PyPackageCreator failed", package=package_name, error=result["stderr"])
                return SpackCreatePypiResult(
                    success=False,
                    message=f"Failed to create PyPI package {package_name}: {result['stderr']}",
                    package_name=package_name,
                    creation_details={
                        "stdout": result["stdout"],
                        "stderr": result["stderr"],
                        "returncode": result["returncode"],
                    },
                )

            # Step 2: Find and move the created package to session directory (if session_id provided)
            moved_to = None
            recipe_path = None

            if session_id:
                session_manager = get_session_manager()
                session_dir = session_manager.get_session_dir(session_id)

                if session_dir is None:
                    logger.error("Session not found", session_id=session_id)
                    return SpackCreatePypiResult(
                        success=False,
                        message=f"Session {session_id} not found",
                        package_name=package_name,
                        creation_details={"error": "Session not found"},
                    )

                # Look for created py-* package in packages directory
                packages_dir = creator_dir / "packages"
                py_packages = list(packages_dir.glob(f"py-{package_name}*"))

                if not py_packages:
                    # Try without py- prefix in case it was created differently
                    py_packages = list(packages_dir.glob("py-*"))

                if py_packages:
                    # Take the first matching package (there should only be one new one)
                    source_package = py_packages[0]

                    # Ensure session spack-repo packages directory exists
                    session_packages_dir = session_dir / "spack-repo" / "packages"
                    session_packages_dir.mkdir(exist_ok=True)

                    # Move to session spack-repo packages directory
                    destination = session_packages_dir / source_package.name

                    # Use mv command to move the directory
                    mv_cmd = ["mv", str(source_package), str(destination)]
                    mv_result = await self._run_command(mv_cmd, timeout=30)

                    if mv_result["success"]:
                        moved_to = str(destination.relative_to(session_dir))
                        recipe_path = str(destination / "package.py")
                        logger.info(
                            "Package moved to session",
                            package=package_name,
                            source=str(source_package),
                            destination=str(destination),
                        )
                    else:
                        logger.error(
                            "Failed to move package to session", package=package_name, error=mv_result["stderr"]
                        )
                        return SpackCreatePypiResult(
                            success=False,
                            message=(
                                f"PyPackageCreator created the package but failed to move it to session: "
                                f"{mv_result['stderr']}"
                            ),
                            package_name=package_name,
                            creation_details={
                                "stdout": result["stdout"],
                                "stderr": result["stderr"],
                                "mv_error": mv_result["stderr"],
                                "error": "Failed to move package to session",
                            },
                        )
                else:
                    logger.error("No py- packages found after creation", package=package_name)
                    return SpackCreatePypiResult(
                        success=False,
                        message=f"PyPackageCreator completed but no py-{package_name} package was found in the output",
                        package_name=package_name,
                        creation_details={
                            "stdout": result["stdout"],
                            "stderr": result["stderr"],
                            "error": "No py- package found after creation",
                        },
                    )

            logger.success("PyPI package created successfully", package=package_name, moved_to=moved_to)

            return SpackCreatePypiResult(
                success=True,
                message=f"Successfully created PyPI package {package_name}"
                + (f" and moved to session {session_id}" if moved_to else ""),
                package_name=package_name,
                recipe_path=recipe_path,
                moved_to=moved_to,
                creation_details={
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                    "session_id": session_id,
                    "creator_script": str(creator_script),
                },
            )

        except Exception as e:
            logger.exception("PyPI package creation failed", package=package_name, error=str(e))
            return SpackCreatePypiResult(
                success=False,
                message=f"Failed to create PyPI package {package_name}: {str(e)}",
                package_name=package_name,
                creation_details={"error": str(e)},
            )

    async def copy_existing_package(
        self,
        package_name: str,
        session_id: str,
    ) -> SpackCopyPackageResult:
        """
        Copy an existing spack package without using spack create.

        This method mimics the create() function from .zshrc but skips the spack create step.
        It copies an existing package from the builtin packages to the session directory.

        Args:
            package_name: Name of the package to copy
            session_id: Session ID for isolated execution

        Returns:
            Copy result with details
        """
        logger.info("Copying existing package", package=package_name, session_id=session_id)

        try:
            # Get session directory
            session_manager = get_session_manager()
            session_dir = session_manager.get_session_dir(session_id)

            if session_dir is None:
                logger.error("Session not found", session_id=session_id)
                return SpackCopyPackageResult(
                    success=False,
                    message=f"Session {session_id} not found",
                    package_name=package_name,
                    copy_details={"error": "Session not found"},
                )

            # Convert package name for source directory (replace hyphens with underscores)
            replace_pkg = package_name.replace("-", "_")

            # Source directory in builtin packages
            src_dir = (
                Path.home() / "work" / "spack-packages" / "repos" / "spack_repo" / "builtin" / "packages" / replace_pkg
            )

            # Navigate to the spack directory and checkout the legacy commit
            spack_dir = Path.home() / "work" / "spack-packages"
            logger.info(
                "Checking out legacy spack commit",
                commit="78f95ff38d591cbe956a726f4a93f57d21840f86",
                spack_dir=str(spack_dir),
            )

            git_checkout_cmd = ["git", "checkout", "78f95ff38d591cbe956a726f4a93f57d21840f86"]
            git_result = await self._run_command(git_checkout_cmd, cwd=spack_dir, timeout=60)

            if not git_result["success"]:
                logger.error(
                    "Git checkout failed", commit="78f95ff38d591cbe956a726f4a93f57d21840f86", error=git_result["stderr"]
                )
                return SpackCopyPackageResult(
                    success=False,
                    message=f"Failed to checkout legacy spack commit: {git_result['stderr']}",
                    package_name=package_name,
                    copy_details={
                        "error": "Git checkout failed",
                        "git_stderr": git_result["stderr"],
                        "git_stdout": git_result["stdout"],
                    },
                )

            logger.info(
                "Successfully checked out legacy spack commit", commit="78f95ff38d591cbe956a726f4a93f57d21840f86"
            )

            # Destination directory in session
            dest_dir = session_dir / "spack-repo" / "packages" / package_name

            # Check if source package exists
            if not src_dir.exists():
                logger.error("Source package not found", package=package_name, src_dir=str(src_dir))
                return SpackCopyPackageResult(
                    success=False,
                    message=f"Source package '{package_name}' not found in builtin packages",
                    package_name=package_name,
                    copy_details={"error": "Source package not found", "src_dir": str(src_dir)},
                )

            # Ensure destination directory exists
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Copy package.py file
            src_package_py = src_dir / "package.py"
            dest_package_py = dest_dir / "package.py"

            if not src_package_py.exists():
                logger.error("package.py not found in source", package=package_name, src_package_py=str(src_package_py))
                return SpackCopyPackageResult(
                    success=False,
                    message=f"package.py not found for '{package_name}' in source directory",
                    package_name=package_name,
                    copy_details={"error": "package.py not found in source", "src_package_py": str(src_package_py)},
                )

            # Copy package.py file
            shutil.copy2(src_package_py, dest_package_py)

            # Copy any .patch files
            patch_files = []
            for patch_file in src_dir.glob("*.patch"):
                dest_patch = dest_dir / patch_file.name
                shutil.copy2(patch_file, dest_patch)
                patch_files.append(patch_file.name)

            # Apply the same modifications as in the .zshrc create function
            package_content = dest_package_py.read_text(encoding="utf-8")

            # Comment out specific depends_on lines
            package_content = package_content.replace(
                'depends_on("c", type="build")', '# depends_on("c", type="build")'
            )
            package_content = package_content.replace(
                'depends_on("cxx", type="build")', '# depends_on("cxx", type="build")'
            )
            package_content = package_content.replace(
                'depends_on("fortran", type="build")', '# depends_on("fortran", type="build")'
            )

            # Remove : EnvironmentModifications
            package_content = package_content.replace(": EnvironmentModifications", "")

            # Remove checked_by from license lines while preserving the final parenthesis
            package_content = re.sub(r"license\(([^)]*), *checked_by=[^)]*\)", r"license(\1)", package_content)

            # Comment out lines starting with 'from spack_repo.builtin'
            lines = package_content.split("\n")
            modified_lines = []
            for line in lines:
                if line.strip().startswith("from spack_repo.builtin"):
                    # Add comment prefix while preserving indentation
                    indent = len(line) - len(line.lstrip())
                    modified_lines.append(" " * indent + "# " + line.strip())
                else:
                    modified_lines.append(line)
            package_content = "\n".join(modified_lines)

            # Write the modified content back
            dest_package_py.write_text(package_content, encoding="utf-8")

            logger.success(
                "Package copied successfully",
                package=package_name,
                src_dir=str(src_dir),
                dest_dir=str(dest_dir),
                patch_files=patch_files,
            )

            return SpackCopyPackageResult(
                success=True,
                message=f"Successfully copied package '{package_name}' to session {session_id}",
                package_name=package_name,
                source_path=str(src_dir.relative_to(Path.home() / "work" / "spack-packages")),
                destination_path=str(dest_dir.relative_to(session_dir)),
                recipe_path=str(dest_package_py.relative_to(session_dir)),
                copy_details={
                    "src_dir": str(src_dir),
                    "dest_dir": str(dest_dir),
                    "patch_files": patch_files,
                    "legacy_commit": "78f95ff38d591cbe956a726f4a93f57d21840f86",
                    "git_checkout_success": True,
                    "modifications_applied": [
                        "commented_out_c_cxx_fortran_dependencies",
                        "removed_environment_modifications",
                        "removed_checked_by_from_licenses",
                        "commented_out_spack_repo_builtin_imports",
                    ],
                },
            )

        except Exception as e:
            logger.exception("Package copy failed", package=package_name, session_id=session_id, error=str(e))
            return SpackCopyPackageResult(
                success=False,
                message=f"Failed to copy package '{package_name}': {str(e)}",
                package_name=package_name,
                copy_details={"error": str(e)},
            )

    async def get_package_info(
        self,
        package_name: str,
        version: str | None = None,
        session_id: str | None = None,
    ) -> SpackPackage:
        """
        Get comprehensive package information including dependencies and build details.

        Args:
            package_name: Package name
            version: Package version
            session_id: Optional session ID for isolated execution

        Returns:
            Complete package information
        """
        spec = package_name
        if version:
            spec += f"@{version}"

        logger.info("Getting package info", package=spec, session_id=session_id)

        cmd = [str(self.spack_cmd), "info", spec]
        result = await self._run_spack_command(cmd, session_id=session_id)

        if not result["success"]:
            logger.error("Failed to get package info", package=spec, error=result["stderr"])
            return SpackPackage(
                name=package_name,
                version=version or "unknown",
                description="Package information unavailable",
                homepage="",
                variants=[],
                dependencies=[],
            )

        # Parse the comprehensive info output
        lines = result["stdout"].split("\n")
        package_type = ""
        description = ""
        homepage = ""
        preferred_version = None
        safe_versions = []
        deprecated_versions = []
        variants = []
        build_dependencies = []
        link_dependencies = []
        run_dependencies = []
        licenses = []
        all_dependencies = []  # For backward compatibility

        multiline_description = ""

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Package type (first line, e.g., "PythonPackage:   py-pandas")
            if i == 0 and ":" in line and not line.startswith(" "):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    package_type = parts[0].strip()

            # Description section (can be multiline)
            elif line.startswith("Description:"):
                description = line.replace("Description:", "").strip()
                # Check for multiline description
                i += 1
                excluded_starts = ("Homepage:", "Preferred version:", "Safe versions:")
                while (
                    i < len(lines) and lines[i].startswith("    ") and not lines[i].strip().startswith(excluded_starts)
                ):
                    multiline_description += " " + lines[i].strip()
                    i += 1
                i -= 1  # Back up one since the loop will increment
                if multiline_description:
                    description += multiline_description

            # Homepage
            elif line.startswith("Homepage:"):
                homepage = line.replace("Homepage:", "").strip()

            # Preferred version
            elif line.startswith("Preferred version:"):
                i += 1
                if i < len(lines):
                    version_line = lines[i].strip()
                    if version_line:
                        parts = version_line.split()
                        if len(parts) >= 1:
                            preferred_version = SpackVersionInfo(
                                version=parts[0], url=parts[1] if len(parts) > 1 else None
                            )

            # Safe versions
            elif line.startswith("Safe versions:"):
                i += 1
                while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                    version_line = lines[i].strip()
                    if version_line and not version_line.startswith(("Deprecated versions:", "Variants:")):
                        parts = version_line.split()
                        if len(parts) >= 1:
                            safe_versions.append(
                                SpackVersionInfo(version=parts[0], url=parts[1] if len(parts) > 1 else None)
                            )
                    i += 1
                i -= 1

            # Deprecated versions
            elif line.startswith("Deprecated versions:"):
                i += 1
                while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                    version_line = lines[i].strip()
                    if version_line and version_line != "None":
                        parts = version_line.split()
                        if len(parts) >= 1:
                            deprecated_versions.append(
                                SpackVersionInfo(version=parts[0], url=parts[1] if len(parts) > 1 else None)
                            )
                    i += 1
                i -= 1

            # Variants section
            elif line.startswith("Variants:"):
                i += 1
                current_variant = None
                while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                    variant_line = lines[i].strip()
                    if not variant_line:
                        i += 1
                        continue

                    if variant_line.startswith("when @"):
                        # Handle conditional variants
                        if current_variant:
                            current_variant.conditional = variant_line
                    elif "[" in variant_line and "]" in variant_line:
                        # New variant definition
                        if current_variant:
                            variants.append(current_variant)

                        # Parse variant: name [default] values description
                        bracket_start = variant_line.find("[")
                        bracket_end = variant_line.find("]")

                        if bracket_start > 0 and bracket_end > bracket_start:
                            variant_name = variant_line[:bracket_start].strip()
                            default_val = variant_line[bracket_start + 1 : bracket_end].strip()
                            remaining = variant_line[bracket_end + 1 :].strip()

                            # Parse possible values and description
                            values = []
                            description_part = ""
                            if remaining:
                                # Look for comma-separated values
                                if "," in remaining:
                                    values = [v.strip() for v in remaining.split(",")]
                                else:
                                    # Single value or description
                                    values = [remaining] if remaining and not remaining[0].isupper() else []
                                    description_part = remaining if remaining and remaining[0].isupper() else ""

                            current_variant = SpackVariant(
                                name=variant_name, default=default_val, values=values, description=description_part
                            )
                    i += 1

                # Add the last variant
                if current_variant:
                    variants.append(current_variant)
                i -= 1

            # Build Dependencies
            elif line.startswith("Build Dependencies:"):
                i += 1
                while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                    deps_line = lines[i].strip()
                    if deps_line and deps_line != "None":
                        # Split by whitespace to get individual dependencies
                        deps = deps_line.split()
                        build_dependencies.extend(deps)
                        all_dependencies.extend(deps)
                    i += 1
                i -= 1

            # Link Dependencies
            elif line.startswith("Link Dependencies:"):
                i += 1
                while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                    deps_line = lines[i].strip()
                    if deps_line and deps_line != "None":
                        deps = deps_line.split()
                        link_dependencies.extend(deps)
                        all_dependencies.extend(deps)
                    i += 1
                i -= 1

            # Run Dependencies
            elif line.startswith("Run Dependencies:"):
                i += 1
                while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                    deps_line = lines[i].strip()
                    if deps_line and deps_line != "None":
                        deps = deps_line.split()
                        run_dependencies.extend(deps)
                        all_dependencies.extend(deps)
                    i += 1
                i -= 1

            # Licenses
            elif line.startswith("Licenses:"):
                license_line = line.replace("Licenses:", "").strip()
                if license_line and license_line != "None":
                    licenses = [license_line]
                else:
                    # License on next line
                    i += 1
                    if i < len(lines):
                        next_line = lines[i].strip()
                        if next_line and next_line != "None":
                            licenses = [next_line]

            i += 1

        return SpackPackage(
            name=package_name,
            version=version or "latest",
            package_type=package_type or None,
            description=description or f"Spack package: {package_name}",
            homepage=homepage or None,
            preferred_version=preferred_version,
            safe_versions=safe_versions,
            deprecated_versions=deprecated_versions,
            variants=variants,
            build_dependencies=build_dependencies,
            link_dependencies=link_dependencies,
            run_dependencies=run_dependencies,
            licenses=licenses,
            dependencies=list(set(all_dependencies)),  # Remove duplicates for backward compatibility
        )


# Global service instance
_spack_service: SpackService | None = None


def get_spack_service() -> SpackService:
    """Get the global spack service instance."""
    global _spack_service
    if _spack_service is None:
        settings = get_settings()
        _spack_service = SpackService(spack_executable=settings.spack_executable)
    return _spack_service
