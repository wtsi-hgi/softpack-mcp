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
    SpackChecksumResult,
    SpackCopyPackageResult,
    SpackCreateFromUrlResult,
    SpackCreatePypiResult,
    SpackInstallStreamResult,
    SpackPackage,
    SpackUninstallAllResult,
    SpackValidationResult,
    SpackValidationStreamResult,
    SpackVariant,
    SpackVersionInfo,
    SpackVersionsResult,
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

    def _extract_install_digest(self, output: str) -> str | None:
        """
        Extract the installation digest from spack install output.

        Args:
            output: The stdout/stderr output from spack install

        Returns:
            The digest hash if found, None otherwise
        """
        import re

        # Normalize the output - handle different line endings and whitespace
        output = output.replace("\r\n", "\n").replace("\r", "\n")

        # Pattern to match the installation path with digest
        # Example: [+] /home/ubuntu/.spack/linux-ubuntu22.04-skylake_avx512/gcc-11.4.0/
        # py-dit-1.5-gbt2624om2fm2r6lvokqqtuuw4tf2xcd
        # We need to extract just the digest part (last 32-33 characters after the last dash)
        # IMPORTANT: Look for the LAST occurrence since that's the package we're actually installing
        pattern = r"\[\+\]\s+[^\s]+/([^/\s]+)"
        matches = list(re.finditer(pattern, output))

        if matches:
            # Take the last match (most recent installation)
            match = matches[-1]
            full_package_name = match.group(1).strip()
            logger.debug(
                "Extracted package name from installation output (last occurrence)",
                package_name=full_package_name,
            )

            # Extract the digest part (last 32-33 characters after the last dash)
            # Example: py-dit-1.5-gbt2624om2fm2r6lvokqqtuuw4tf2xcd -> gbt2624om2fm2r6lvokqqtuuw4tf2xcd
            parts = full_package_name.split("-")

            if len(parts) > 1:
                digest = parts[-1].strip()
                logger.debug("Extracted digest candidate", digest=digest, length=len(digest))

                # Verify it's exactly a 32-character alphanumeric string
                if len(digest) == 32 and digest.isalnum():
                    logger.info("Successfully extracted installation digest", digest=digest)
                    return digest
                else:
                    logger.debug(
                        "Digest validation failed", digest=digest, length=len(digest), isalnum=digest.isalnum()
                    )
            else:
                logger.debug("Package name has insufficient parts for digest extraction", parts=parts)
        else:
            logger.debug("No [+] installation path found in output")

        return None

    def _extract_install_digest_robust(self, output: str) -> str | None:
        """
        More robust extraction of installation digest from spack install output.

        This method tries multiple patterns and handles edge cases better.

        Args:
            output: The stdout/stderr output from spack install

        Returns:
            The digest hash if found, None otherwise
        """
        import re

        # Normalize the output
        output = output.replace("\r\n", "\n").replace("\r", "\n")

        # Try multiple patterns to find the installation path
        patterns = [
            # Pattern 1: Standard [+] /path/to/package format
            r"\[\+\]\s+([^\s]+)$",
            # Pattern 2: More flexible pattern that doesn't require end of line
            r"\[\+\]\s+([^\s]+)",
            # Pattern 3: Look for the last occurrence of [+] in the output
            r"\[\+\]\s+([^\s]+)",
        ]

        for i, pattern in enumerate(patterns):
            matches = list(re.finditer(pattern, output, re.MULTILINE))
            if matches:
                # Always take the last match (most recent installation)
                match = matches[-1]
                full_path = match.group(1).strip()

                logger.debug(f"Pattern {i+1} matched", full_path=full_path)

                # Extract the last component (package name with digest)
                if "/" in full_path:
                    package_name = full_path.split("/")[-1].strip()
                else:
                    package_name = full_path.strip()

                logger.debug("Extracted package name", package_name=package_name)

                # Extract the digest part (last 32-33 characters after the last dash)
                parts = package_name.split("-")

                if len(parts) > 1:
                    digest = parts[-1].strip()
                    logger.debug("Extracted digest candidate", digest=digest, length=len(digest))

                    # Verify it's exactly a 32-character alphanumeric string
                    if len(digest) == 32 and digest.isalnum():
                        logger.info("Successfully extracted installation digest", digest=digest, pattern_used=i + 1)
                        return digest
                    else:
                        logger.debug(
                            "Digest validation failed", digest=digest, length=len(digest), isalnum=digest.isalnum()
                        )
                else:
                    logger.debug("Package name has insufficient parts for digest extraction", parts=parts)

        logger.debug("No valid installation digest found in output")
        return None

    def _collect_build_logs_from_output(self, full_output: str) -> str | None:
        """Collect spack build logs referenced in output or via recent stage dirs.

        Searches the provided output for explicit spack build log file paths as well as
        stage directory paths, and attempts to read their corresponding
        `spack-build-out.txt` files. Falls back to scanning recent stage directories
        under `/tmp/*/spack-stage/` when none are discovered in output.

        Returns a single concatenated string of the collected logs, or None if none
        could be found.
        """
        try:
            import re

            stage_paths: list[str] = []
            log_file_paths: list[str] = []

            # Look for explicit spack-build-out.txt file paths in the output
            explicit_log_pattern = r"/tmp/[^/\s]*/spack-stage/spack-stage-[^/\s]+/spack-build-out\.txt"
            explicit_logs = re.findall(explicit_log_pattern, full_output)
            log_file_paths.extend(explicit_logs)

            # Look for spack-stage directory paths in the output
            stage_pattern = r"/tmp/[^/\s]*/spack-stage/spack-stage-[^/\s]+"
            matches = re.findall(stage_pattern, full_output)
            stage_paths.extend(matches)

            # Also look for other common spack build directory patterns
            build_pattern = r"/tmp/[^/\s]*/spack-build-[^/\s]+"
            matches = re.findall(build_pattern, full_output)
            stage_paths.extend(matches)

            # If no paths found in output, search for recent stage directories
            if not stage_paths and not log_file_paths:
                logger.warning("No stage or log paths found in output, searching filesystem")
                import glob

                recent_stages = glob.glob("/tmp/*/spack-stage/spack-stage-*")
                # Sort by modification time, get most recent ones
                recent_stages.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)
                stage_paths.extend(recent_stages[:5])  # Take 5 most recent
                logger.info(f"Found {len(stage_paths)} recent stage directories")

            # Build a unique, ordered list of candidate log files
            candidate_logs: list[Path] = []
            seen: set[str] = set()

            for file_path in log_file_paths:
                if file_path not in seen:
                    candidate_logs.append(Path(file_path))
                    seen.add(file_path)

            for stage_path in stage_paths:
                file_path = str(Path(stage_path) / "spack-build-out.txt")
                if file_path not in seen:
                    candidate_logs.append(Path(file_path))
                    seen.add(file_path)

            logs: list[str] = []
            for log_file in candidate_logs:
                if log_file.exists():
                    try:
                        content = log_file.read_text(encoding="utf-8")
                        logs.append(f"===== {log_file} =====\n" + content)
                        logger.info(f"Successfully read build log: {log_file} ({len(content)} chars)")
                    except Exception as e:  # noqa: BLE001
                        error_msg = f"===== {log_file} (error reading: {e}) =====\n"
                        logs.append(error_msg)
                        logger.warning(f"Failed to read build log {log_file}: {e}")
                else:
                    logger.debug(f"Build log not found: {log_file}")

            if logs:
                logger.info(f"Collected {len(logs)} build logs for detailed_failed_log")
                return "\n\n".join(logs)
            else:
                logger.warning("No spack-build-out.txt files found in discovered locations")
                return None
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to collect spack-build-out.txt logs: {e}")
            return None

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

            # Extract installation digest from output
            install_digest = self._extract_install_digest(result["stdout"] + result["stderr"])
            if not install_digest:
                # Try the more robust method as fallback
                install_digest = self._extract_install_digest_robust(result["stdout"] + result["stderr"])

            if install_digest:
                logger.info("Extracted installation digest", package=spec, digest=install_digest)
            detailed_failed_log = None
        else:
            logger.error("Package installation failed", package=spec, error=result["stderr"])
            message = f"Failed to install {spec}: {result['stderr']}"
            install_digest = None
            # Collect spack-build-out.txt from the build directory mentioned in output
            full_output = result["stdout"] + result["stderr"]
            detailed_failed_log = self._collect_build_logs_from_output(full_output)
        return OperationResult(
            success=result["success"],
            message=message,
            details={
                "package": spec,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "install_digest": install_digest,
            },
            detailed_failed_log=detailed_failed_log,
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
            all_output = []  # Collect all output for digest extraction

            # Function to read from a stream and put results in queue
            async def read_stream(stream: asyncio.StreamReader, stream_type: str):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    line_data = line.decode("utf-8").rstrip()
                    all_output.append(line_data)
                    await output_queue.put(
                        SpackInstallStreamResult(
                            type=stream_type,
                            data=line_data,
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

                # Extract installation digest from all collected output
                install_digest = self._extract_install_digest("\n".join(all_output))
                if not install_digest:
                    # Try the more robust method as fallback
                    install_digest = self._extract_install_digest_robust("\n".join(all_output))

                if install_digest:
                    logger.info("Extracted installation digest", package=spec, digest=install_digest)
                detailed_failed_log = None
            else:
                logger.error("Package installation failed", package=spec, returncode=returncode)
                message = f"Failed to install {spec} (return code: {returncode})"
                install_digest = None
                # Collect spack-build-out.txt from the build directory mentioned in output
                full_output = "\n".join(all_output)
                detailed_failed_log = self._collect_build_logs_from_output(full_output)
            yield SpackInstallStreamResult(
                type="complete",
                data=message,
                timestamp=time.time(),
                package_name=package_name,
                version=version,
                success=success,
                install_digest=install_digest,
                detailed_failed_log=detailed_failed_log if not success else None,
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
            moved_packages = []
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
                # Always use the broader pattern to capture all packages created by PyPackageCreator
                # including dependencies, not just the main package
                py_packages = list(packages_dir.glob("py-*"))

                if py_packages:
                    # Move all created packages to session (PyPackageCreator can create multiple recipes)
                    session_packages_dir = session_dir / "spack-repo" / "packages"
                    session_packages_dir.mkdir(exist_ok=True)

                    for source_package in py_packages:
                        # Move to session spack-repo packages directory
                        destination = session_packages_dir / source_package.name

                        # Use mv command to move the directory
                        mv_cmd = ["mv", str(source_package), str(destination)]
                        mv_result = await self._run_command(mv_cmd, timeout=30)

                        if mv_result["success"]:
                            moved_packages.append(
                                {
                                    "name": source_package.name,
                                    "path": str(destination.relative_to(session_dir)),
                                    "recipe_path": str(destination / "package.py"),
                                }
                            )
                            logger.info(
                                "Package moved to session",
                                package=source_package.name,
                                source=str(source_package),
                                destination=str(destination),
                            )
                        else:
                            logger.error(
                                "Failed to move package to session",
                                package=source_package.name,
                                error=mv_result["stderr"],
                            )

                    if moved_packages:
                        # Set the main package as the primary one
                        main_package = next(
                            (p for p in moved_packages if p["name"] == f"py-{package_name}"), moved_packages[0]
                        )
                        moved_to = main_package["path"]
                        recipe_path = main_package["recipe_path"]

                        logger.info(
                            "All packages moved to session",
                            total_moved=len(moved_packages),
                            packages=[p["name"] for p in moved_packages],
                        )
                    else:
                        logger.error("Failed to move any packages to session", package=package_name)
                        return SpackCreatePypiResult(
                            success=False,
                            message="PyPackageCreator created packages but failed to move them to session",
                            package_name=package_name,
                            creation_details={
                                "stdout": result["stdout"],
                                "stderr": result["stderr"],
                                "error": "Failed to move packages to session",
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
                moved_packages=moved_packages if moved_packages else None,
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

            # For Python packages, try different naming conventions
            if package_name.startswith("py-"):
                # Try the original name first (py-numpy -> py_numpy)
                src_dir = (
                    Path.home()
                    / "work"
                    / "spack-packages"
                    / "repos"
                    / "spack_repo"
                    / "builtin"
                    / "packages"
                    / replace_pkg
                )

                # If not found, try without py- prefix (py-numpy -> numpy)
                if not src_dir.exists():
                    alt_replace_pkg = package_name.replace("py-", "").replace("-", "_")
                    src_dir = (
                        Path.home()
                        / "work"
                        / "spack-packages"
                        / "repos"
                        / "spack_repo"
                        / "builtin"
                        / "packages"
                        / alt_replace_pkg
                    )
                    logger.info(f"Trying alternative package name: '{package_name}' -> '{alt_replace_pkg}'")

                    # If still not found, try with just the base name (py-numpy -> numpy)
                    if not src_dir.exists():
                        base_name = package_name.replace("py-", "")
                        src_dir = (
                            Path.home()
                            / "work"
                            / "spack-packages"
                            / "repos"
                            / "spack_repo"
                            / "builtin"
                            / "packages"
                            / base_name
                        )
                        logger.info(f"Trying base package name: '{package_name}' -> '{base_name}'")
            else:
                # Source directory in builtin packages
                src_dir = (
                    Path.home()
                    / "work"
                    / "spack-packages"
                    / "repos"
                    / "spack_repo"
                    / "builtin"
                    / "packages"
                    / replace_pkg
                )

            logger.info(f"Looking for package '{package_name}' in source directory: {src_dir}")
            logger.info(f"Converted package name: '{package_name}' -> '{replace_pkg}'")

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
                logger.error("Source package not found in legacy commit", package=package_name, src_dir=str(src_dir))

                # Try to find the package in the current spack repository with same naming logic
                if package_name.startswith("py-"):
                    # Try the original name first (py-numpy -> py_numpy)
                    current_src_dir = (
                        Path.home()
                        / "work"
                        / "spack-packages"
                        / "repos"
                        / "spack_repo"
                        / "builtin"
                        / "packages"
                        / replace_pkg
                    )

                    # If not found, try without py- prefix (py-numpy -> numpy)
                    if not current_src_dir.exists():
                        alt_replace_pkg = package_name.replace("py-", "").replace("-", "_")
                        current_src_dir = (
                            Path.home()
                            / "work"
                            / "spack-packages"
                            / "repos"
                            / "spack_repo"
                            / "builtin"
                            / "packages"
                            / alt_replace_pkg
                        )
                        logger.info(
                            f"Trying alternative package name in current repo: '{package_name}' -> '{alt_replace_pkg}'"
                        )

                        # If still not found, try with just the base name (py-numpy -> numpy)
                        if not current_src_dir.exists():
                            base_name = package_name.replace("py-", "")
                            current_src_dir = (
                                Path.home()
                                / "work"
                                / "spack-packages"
                                / "repos"
                                / "spack_repo"
                                / "builtin"
                                / "packages"
                                / base_name
                            )
                            logger.info(f"Trying base package name in current repo: '{package_name}' -> '{base_name}'")
                else:
                    current_src_dir = (
                        Path.home()
                        / "work"
                        / "spack-packages"
                        / "repos"
                        / "spack_repo"
                        / "builtin"
                        / "packages"
                        / replace_pkg
                    )

                if current_src_dir.exists():
                    logger.info(f"Found package in current spack repository: {current_src_dir}")
                    src_dir = current_src_dir
                else:
                    logger.error(
                        "Source package not found in current spack repository either",
                        package=package_name,
                        current_src_dir=str(current_src_dir),
                    )

                    # Try to find the package in alternative locations
                    packages_dir = (
                        Path.home() / "work" / "spack-packages" / "repos" / "spack_repo" / "builtin" / "packages"
                    )
                    if packages_dir.exists():
                        available_packages = [p.name for p in packages_dir.iterdir() if p.is_dir()]
                        logger.info(f"Available packages in {packages_dir}: {available_packages}")

                        # Try to find a similar package name
                        similar_packages = [
                            p for p in available_packages if package_name.replace("-", "_") in p or package_name in p
                        ]
                        if similar_packages:
                            logger.info(f"Similar packages found: {similar_packages}")

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

            # Copy all relevant files from the package directory
            copied_files = []
            logger.info(f"Source directory contents: {[item.name for item in src_dir.iterdir()]}")

            for item in src_dir.iterdir():
                if item.is_file():
                    # Copy all files except package.py (already copied above)
                    if item.name != "package.py":
                        dest_file = dest_dir / item.name
                        try:
                            shutil.copy2(item, dest_file)
                            copied_files.append(item.name)
                            logger.info(f"Successfully copied file: {item.name} from {item} to {dest_file}")
                        except Exception as e:
                            logger.error(f"Failed to copy file {item.name}: {e}")
                            # Continue with other files even if one fails
                else:
                    logger.debug(f"Skipping non-file item: {item.name} (type: {type(item)})")

            logger.info(f"Total files copied: {len(copied_files)} - {copied_files}")

            # Verify that patch files were copied
            patch_files = [f for f in copied_files if f.endswith(".patch")]
            if patch_files:
                logger.info(f"Successfully copied patch files: {patch_files}")
            else:
                logger.warning("No patch files found in source directory")
                # Check if there are any .patch files in the source that weren't copied
                source_patch_files = [f.name for f in src_dir.iterdir() if f.is_file() and f.name.endswith(".patch")]
                if source_patch_files:
                    logger.error(f"Patch files exist in source but weren't copied: {source_patch_files}")
                    # Include the source patch files in the response for debugging
                    patch_files = source_patch_files

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
                copied_files=copied_files,
            )

            return SpackCopyPackageResult(
                success=True,
                message=f"Successfully copied package '{package_name}' to session {session_id}",
                package_name=package_name,
                source_path=str(src_dir.relative_to(Path.home() / "work" / "spack-packages")),
                destination_path=str(dest_dir.relative_to(session_dir)),
                recipe_path=str(dest_package_py.relative_to(session_dir)),
                copied_files=copied_files,
                copy_details={
                    "src_dir": str(src_dir),
                    "dest_dir": str(dest_dir),
                    "copied_files": copied_files,
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

    async def get_package_versions(
        self,
        package_name: str,
        session_id: str | None = None,
    ) -> SpackVersionsResult:
        """
        Get available versions for a spack package with checksum information.

        Args:
            package_name: Package name
            session_id: Optional session ID for isolated execution

        Returns:
            Available versions result with checksum status
        """
        logger.info("Getting package versions with checksums", package=package_name, session_id=session_id)

        # First get versions
        cmd = [str(self.spack_cmd), "versions", package_name]
        versions_result = await self._run_spack_command(cmd, session_id=session_id)

        # If session execution fails with "package not found", try without session isolation
        if not versions_result["success"] and session_id and "not found" in versions_result["stderr"]:
            logger.info(
                "Package not found in session for versions, retrying without session isolation",
                package=package_name,
                session_id=session_id,
            )
            versions_result = await self._run_spack_command(cmd, session_id=None)

        if not versions_result["success"]:
            logger.error("Failed to get package versions", package=package_name, error=versions_result["stderr"])
            return SpackVersionsResult(
                success=False,
                message=f"Failed to get versions for {package_name}: {versions_result['stderr']}",
                package_name=package_name,
                versions=[],
                version_info=[],
                version_details={"error": versions_result["stderr"]},
            )

        # Parse versions from output
        versions = []
        lines = versions_result["stdout"].strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("=") and not line.startswith("Safe") and not line.startswith("Deprecated"):
                # Extract version numbers (skip URLs and other info)
                parts = line.split()
                if parts:
                    version = parts[0]
                    if version and not version.startswith("-"):
                        versions.append(version)

        # Now get checksums to see which versions have them
        checksums_result = await self.get_package_checksums(package_name, session_id=session_id)
        available_checksums = checksums_result.checksums if checksums_result.success else {}

        # Create detailed version info
        version_info = []
        for version in versions:
            has_checksum = version in available_checksums
            checksum = available_checksums.get(version) if has_checksum else None

            version_info.append(
                SpackVersionInfo(
                    version=version,
                    url=None,  # URL not available from versions command
                    has_checksum=has_checksum,
                    checksum=checksum,
                )
            )

        logger.success(
            "Retrieved package versions with checksums",
            package=package_name,
            total_versions=len(versions),
            checksummed_versions=len(available_checksums),
        )

        return SpackVersionsResult(
            success=True,
            message=f"Found {len(versions)} versions for {package_name} ({len(available_checksums)} with checksums)",
            package_name=package_name,
            versions=versions,  # Keep for backward compatibility
            version_info=version_info,
            version_details={
                "stdout": versions_result["stdout"],
                "stderr": versions_result["stderr"],
                "checksums_available": len(available_checksums),
                "total_versions": len(versions),
            },
        )

    async def get_package_checksums(
        self,
        package_name: str,
        session_id: str | None = None,
    ) -> SpackChecksumResult:
        """
        Get checksums for a spack package.

        Args:
            package_name: Package name
            session_id: Optional session ID for isolated execution

        Returns:
            Package checksums result
        """
        logger.info("Getting package checksums", package=package_name, session_id=session_id)

        cmd = [str(self.spack_cmd), "checksum", "-b", package_name]
        result = await self._run_spack_command(cmd, session_id=session_id, timeout=600)  # 10 minutes

        # If session execution fails with "package not found", try without session isolation
        # This handles the case where we need checksums for existing packages that aren't in the session yet
        if not result["success"] and session_id and "not found" in result["stderr"]:
            logger.info(
                "Package not found in session, retrying without session isolation",
                package=package_name,
                session_id=session_id,
            )
            result = await self._run_spack_command(cmd, session_id=None, timeout=600)

        if not result["success"]:
            logger.error("Failed to get package checksums", package=package_name, error=result["stderr"])
            return SpackChecksumResult(
                success=False,
                message=f"Failed to get checksums for {package_name}: {result['stderr']}",
                package_name=package_name,
                checksums={},
                checksum_details={"error": result["stderr"]},
            )

        # Parse checksums from output
        checksums = {}
        lines = result["stdout"].strip().split("\n")
        for line in lines:
            line = line.strip()
            # Look for version lines with checksums
            if "version(" in line and "sha256=" in line:
                # Extract version and checksum
                try:
                    version_start = line.find('"') + 1
                    version_end = line.find('"', version_start)
                    version = line[version_start:version_end]

                    sha_start = line.find('sha256="') + 8
                    sha_end = line.find('"', sha_start)
                    checksum = line[sha_start:sha_end]

                    if version and checksum:
                        checksums[version] = checksum
                except Exception:
                    continue

        logger.success("Retrieved package checksums", package=package_name, count=len(checksums))
        return SpackChecksumResult(
            success=True,
            message=f"Found checksums for {len(checksums)} versions of {package_name}",
            package_name=package_name,
            checksums=checksums,
            checksum_details={"stdout": result["stdout"], "stderr": result["stderr"]},
        )

    async def create_recipe_from_url(
        self,
        url: str,
        session_id: str | None = None,
    ) -> SpackCreateFromUrlResult:
        """
        Create a spack recipe from a URL.

        Args:
            url: URL to create recipe from
            session_id: Optional session ID for isolated execution

        Returns:
            Recipe creation result
        """
        logger.info("Creating recipe from URL", url=url, session_id=session_id)

        cmd = [str(self.spack_cmd), "create", "--skip-editor", "-b", url]

        # Handle session-based execution
        working_dir = None
        if session_id:
            session_manager = get_session_manager()
            session_dir = session_manager.get_session_dir(session_id)
            if session_dir:
                working_dir = session_dir / "spack-repo"

        result = await self._run_spack_command(cmd, cwd=working_dir, session_id=session_id, timeout=600)

        if not result["success"]:
            logger.error("Failed to create recipe from URL", url=url, error=result["stderr"])
            return SpackCreateFromUrlResult(
                success=False,
                message=f"Failed to create recipe from {url}: {result['stderr']}",
                url=url,
                creation_details={"error": result["stderr"]},
            )

        # Try to extract package name from output
        package_name = None
        recipe_path = None
        for line in result["stdout"].split("\n"):
            if "Created package" in line or "package.py" in line:
                # Try to extract package name
                parts = line.split()
                for part in parts:
                    if part.endswith("package.py") or "packages/" in part:
                        # Extract package name from path
                        if "/" in part:
                            package_name = part.split("/")[-2] if part.endswith("package.py") else part.split("/")[-1]
                        break

        if package_name and working_dir:
            recipe_path = str((working_dir / "packages" / package_name / "package.py").relative_to(working_dir))

        # Remove Spack boilerplate from generated recipes
        import re

        boilerplate_removed = 0
        if working_dir and (working_dir / "packages").exists():
            package_py_files = list((working_dir / "packages").rglob("package.py"))
            # Improved regex: match any dashed block anywhere in the file
            pattern = r"(?ms)^# -{10,}\n(?:.*?\n)*?# -{10,}(?:\n|$)"
            for pyfile in package_py_files:
                try:
                    content = pyfile.read_text(encoding="utf-8")
                    logger.debug(f"Before boilerplate removal ({pyfile}):\n{content[:200]}")
                    content_cleaned, n = re.subn(pattern, "", content)
                    logger.debug(f"After boilerplate removal ({pyfile}):\n{content_cleaned[:200]}")
                    if n > 0:
                        logger.info(f"Removed {n} Spack boilerplate dashed block(s) from {pyfile}")
                        pyfile.write_text(content_cleaned, encoding="utf-8")
                        boilerplate_removed += n
                except Exception as e:
                    logger.warning(f"Failed to remove boilerplate from {pyfile}: {e}")

        logger.success(
            "Created recipe from URL", url=url, package_name=package_name, boilerplate_removed=boilerplate_removed
        )
        return SpackCreateFromUrlResult(
            success=True,
            message=f"Successfully created recipe from {url}"
            + (f" for package {package_name}" if package_name else "")
            + (f" (removed {boilerplate_removed} boilerplate block(s))" if boilerplate_removed > 0 else ""),
            url=url,
            package_name=package_name,
            recipe_path=recipe_path,
            creation_details={
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "boilerplate_removed": boilerplate_removed,
            },
        )

    async def validate_package(
        self,
        package_name: str,
        package_type: str = "python",
        installation_digest: str | None = None,
        custom_validation_script: str | None = None,
        session_id: str | None = None,
    ) -> SpackValidationResult:
        """
        Validate a spack package installation.

        Args:
            package_name: Package name to validate
            package_type: Type of package (python, r, other)
            installation_digest: Installation digest hash from the installation step
            custom_validation_script: Custom validation script to use instead of default
            session_id: Optional session ID for isolated execution

        Returns:
            Package validation result
        """
        logger.info("Validating package", package=package_name, type=package_type, session_id=session_id)
        logger.info(
            "Received installation_digest parameter",
            installation_digest=installation_digest,
            type=type(installation_digest),
        )

        # Build validation script based on package type or use custom script
        if custom_validation_script:
            validation_script = custom_validation_script
        else:
            validation_scripts = {
                "python": f'python -c "import {package_name}"',
                "r": f'Rscript -e "library({package_name})"',
                "other": "# Check package documentation for validation",
            }
            validation_script = validation_scripts.get(package_type, validation_scripts["other"])

        # Build load command using installation digest if provided
        logger.info(
            "Building load spec",
            installation_digest=installation_digest,
            package_name=package_name,
            package_type=package_type,
        )

        if installation_digest:
            # For spack load, use the first 7 characters of the digest
            # This is the standard spack convention for short hashes
            load_spec = f"/{installation_digest[:7]}"
            logger.info(
                "Using first 7 chars of installation digest for load spec",
                load_spec=load_spec,
                full_digest=installation_digest,
            )
        else:
            # Fallback to recipe name if no digest provided
            prefixes = {"python": "py-", "r": "r-", "other": ""}
            recipe_name = prefixes[package_type] + package_name
            load_spec = recipe_name
            logger.info("Using recipe name for load spec", load_spec=load_spec)

        # Build validation command with session isolation if needed
        if session_id:
            session_manager = get_session_manager()
            try:
                session_dir = session_manager.get_session_dir(session_id)
                if session_dir is None:
                    raise ValueError(f"Session {session_id} not found")

                # Build singularity exec command with session bindings
                validation_command = (
                    f"singularity exec --bind /usr/bin/zsh --bind /mnt/data "
                    f"--bind {session_dir}/repos.yaml:/home/ubuntu/.spack/repos.yaml "
                    f"/home/ubuntu/spack.sif bash -c "
                    f"'source <(/opt/spack/bin/spack load --sh {load_spec}); {validation_script}'"
                )
                cmd = ["bash", "-c", validation_command]
            except ValueError as e:
                logger.error("Failed to get session directory", session_id=session_id, error=str(e))
                return SpackValidationResult(
                    success=False,
                    message=f"Session error: {str(e)}",
                    package_name=package_name,
                    package_type=package_type,
                    validation_command="",
                    validation_output="",
                    validation_details={"error": str(e)},
                )
        else:
            # Build singularity command without session isolation
            validation_command = (
                f"singularity exec --bind /mnt/data /home/ubuntu/spack.sif bash -c "
                f"'source <(/opt/spack/bin/spack load --sh {load_spec}); {validation_script}'"
            )
            cmd = ["bash", "-c", validation_command]

        # Execute validation
        result = await self._run_command(cmd, timeout=300)

        success = result["success"]
        if success:
            logger.success("Package validation successful", package=package_name)
            message = f"Package {package_name} validation successful"
        else:
            logger.error("Package validation failed", package=package_name, error=result["stderr"])
            message = f"Package {package_name} validation failed: {result['stderr']}"

        # Build the actual command that was executed for logging
        actual_command = " ".join(cmd) if isinstance(cmd, list) else cmd

        return SpackValidationResult(
            success=success,
            message=message,
            package_name=package_name,
            package_type=package_type,
            validation_command=actual_command,
            validation_output=result["stdout"],
            validation_details={
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "installation_digest": installation_digest,
                "custom_validation_script": custom_validation_script,
                "load_spec": load_spec,
                "session_id": session_id,
            },
        )

    async def validate_package_stream(
        self,
        package_name: str,
        package_type: str = "python",
        installation_digest: str | None = None,
        custom_validation_script: str | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[SpackValidationStreamResult, None]:
        """
        Validate a spack package installation with streaming output.

        Args:
            package_name: Package name to validate
            package_type: Type of package (python, r, other)
            installation_digest: Installation digest hash from the installation step
            custom_validation_script: Custom validation script to use instead of default
            session_id: Optional session ID for isolated execution

        Yields:
            Streaming validation results
        """
        logger.info("Starting streaming validation", package=package_name, type=package_type, session_id=session_id)
        logger.info(
            "Received installation_digest parameter",
            installation_digest=installation_digest,
            type=type(installation_digest),
        )

        # Send initial status
        yield SpackValidationStreamResult(
            type="start",
            data=f"Starting validation of {package_name}" + (f" (session: {session_id})" if session_id else ""),
            timestamp=time.time(),
            package_name=package_name,
            package_type=package_type,
        )

        # Build validation script based on package type or use custom script
        if custom_validation_script:
            validation_script = custom_validation_script
        else:
            validation_scripts = {
                "python": f'python -c "import {package_name}"',
                "r": f'Rscript -e "library({package_name})"',
                "other": "# Check package documentation for validation",
            }
            validation_script = validation_scripts.get(package_type, validation_scripts["other"])

        # Build load command using installation digest if provided
        logger.info(
            "Building load spec for streaming validation",
            installation_digest=installation_digest,
            package_name=package_name,
            package_type=package_type,
        )

        if installation_digest:
            # For spack load, use the first 7 characters of the digest
            # This is the standard spack convention for short hashes
            load_spec = f"/{installation_digest[:7]}"
            logger.info(
                "Using first 7 chars of installation digest for load spec",
                load_spec=load_spec,
                full_digest=installation_digest,
            )
        else:
            # Fallback to recipe name if no digest provided
            prefixes = {"python": "py-", "r": "r-", "other": ""}
            recipe_name = prefixes[package_type] + package_name
            load_spec = recipe_name
            logger.info("Using recipe name for load spec", load_spec=load_spec)

        # Build validation command with session isolation if needed
        if session_id:
            session_manager = get_session_manager()
            try:
                session_dir = session_manager.get_session_dir(session_id)
                if session_dir is None:
                    raise ValueError(f"Session {session_id} not found")

                # Build singularity exec command with session bindings
                validation_command = (
                    f"singularity exec --bind /usr/bin/zsh --bind /mnt/data "
                    f"--bind {session_dir}/repos.yaml:/home/ubuntu/.spack/repos.yaml "
                    f"/home/ubuntu/spack.sif bash -c "
                    f"'source <(/opt/spack/bin/spack load --sh {load_spec}); {validation_script}'"
                )
                cmd = ["bash", "-c", validation_command]
            except ValueError as e:
                logger.error("Failed to get session directory", session_id=session_id, error=str(e))
                yield SpackValidationStreamResult(
                    type="error",
                    data=f"Session error: {str(e)}",
                    timestamp=time.time(),
                    package_name=package_name,
                    package_type=package_type,
                )
                return
        else:
            # Build singularity command without session isolation
            validation_command = (
                f"singularity exec --bind /mnt/data /home/ubuntu/spack.sif bash -c "
                f"'source <(/opt/spack/bin/spack load --sh {load_spec}); {validation_script}'"
            )
            cmd = ["bash", "-c", validation_command]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Create a queue to collect output from both streams
            output_queue = asyncio.Queue()
            all_output = []  # Collect all output

            # Function to read from a stream and put results in queue
            async def read_stream(stream: asyncio.StreamReader, stream_type: str):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    line_data = line.decode("utf-8").rstrip()
                    all_output.append(line_data)
                    await output_queue.put(
                        SpackValidationStreamResult(
                            type=stream_type,
                            data=line_data,
                            timestamp=time.time(),
                            package_name=package_name,
                            package_type=package_type,
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
                logger.success("Package validation successful", package=package_name)
                message = f"Package {package_name} validation successful"
            else:
                logger.error("Package validation failed", package=package_name, returncode=returncode)
                message = f"Package {package_name} validation failed (return code: {returncode})"

            # Build the actual command that was executed for logging
            actual_command = " ".join(cmd) if isinstance(cmd, list) else cmd

            yield SpackValidationStreamResult(
                type="complete",
                data=message,
                timestamp=time.time(),
                package_name=package_name,
                package_type=package_type,
                success=success,
                validation_command=actual_command,
            )

        except Exception as e:
            logger.exception("Streaming validation failed", package=package_name, error=str(e))
            yield SpackValidationStreamResult(
                type="error",
                data=f"Validation failed: {str(e)}",
                timestamp=time.time(),
                package_name=package_name,
                package_type=package_type,
            )

    async def uninstall_package_with_dependents(
        self,
        package_name: str,
        session_id: str | None = None,
    ) -> SpackUninstallAllResult:
        """
        Uninstall a spack package and all its dependents.

        Args:
            package_name: Package name to uninstall
            session_id: Optional session ID for isolated execution

        Returns:
            Uninstall result with details
        """
        logger.info("Uninstalling package with dependents", package=package_name, session_id=session_id)

        cmd = [str(self.spack_cmd), "uninstall", "-y", "--all", "--dependents", package_name]
        result = await self._run_spack_command(cmd, session_id=session_id, timeout=600)

        if not result["success"]:
            logger.error("Failed to uninstall package with dependents", package=package_name, error=result["stderr"])
            return SpackUninstallAllResult(
                success=False,
                message=f"Failed to uninstall {package_name} and dependents: {result['stderr']}",
                package_name=package_name,
                uninstalled_packages=[],
                uninstall_details={"error": result["stderr"]},
            )

        # Parse uninstalled packages from output
        uninstalled_packages = []
        for line in result["stdout"].split("\n"):
            line = line.strip()
            if "Removing" in line or "uninstalling" in line:
                # Try to extract package name
                parts = line.split()
                for part in parts:
                    if "@" in part or "/" in part:
                        # Extract package name before @ or /
                        pkg = part.split("@")[0].split("/")[-1]
                        if pkg and pkg not in uninstalled_packages:
                            uninstalled_packages.append(pkg)

        logger.success("Uninstalled package with dependents", package=package_name, count=len(uninstalled_packages))
        return SpackUninstallAllResult(
            success=True,
            message=f"Successfully uninstalled {package_name} and {len(uninstalled_packages)} dependent packages",
            package_name=package_name,
            uninstalled_packages=uninstalled_packages,
            uninstall_details={"stdout": result["stdout"], "stderr": result["stderr"]},
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
