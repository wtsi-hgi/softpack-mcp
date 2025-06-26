"""
Spack service implementation.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from ..config import Settings
from ..models.responses import (
    SpackBuildInfo,
    SpackPackage,
)

logger = logging.getLogger(__name__)


class SpackService:
    """Service for managing spack packages and builds."""

    def __init__(self, settings: Settings):
        """Initialize the spack service."""
        self.settings = settings
        self.spack_executable = settings.spack_executable

    async def _run_command(
        self, command: list[str], cwd: Path | None = None, timeout: int | None = None
    ) -> dict[str, Any]:
        """
        Run a shell command asynchronously.

        Args:
            command: Command and arguments to run
            cwd: Working directory
            timeout: Command timeout in seconds

        Returns:
            Command execution result
        """
        start_time = asyncio.get_event_loop().time()
        timeout = timeout or self.settings.command_timeout

        try:
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

            execution_time = asyncio.get_event_loop().time() - start_time

            return {
                "command": " ".join(command),
                "exit_code": process.returncode or 0,
                "stdout": stdout.decode("utf-8") if stdout else "",
                "stderr": stderr.decode("utf-8") if stderr else "",
                "execution_time": execution_time,
                "working_directory": str(cwd) if cwd else None,
            }

        except asyncio.TimeoutError:
            logger.error(f"Command timed out: {' '.join(command)}")
            execution_time = asyncio.get_event_loop().time() - start_time
            return {
                "command": " ".join(command),
                "exit_code": 124,  # Timeout exit code
                "stdout": "",
                "stderr": "Command timed out",
                "execution_time": execution_time,
                "working_directory": str(cwd) if cwd else None,
            }
        except Exception as e:
            logger.error(f"Command failed: {' '.join(command)}: {e}")
            execution_time = asyncio.get_event_loop().time() - start_time
            return {
                "command": " ".join(command),
                "exit_code": 1,
                "stdout": "",
                "stderr": str(e),
                "execution_time": execution_time,
                "working_directory": str(cwd) if cwd else None,
            }

    async def search_packages(self, query: str = "", limit: int = 10) -> list[SpackPackage]:
        """
        Search for spack packages.

        Args:
            query: Search query
            limit: Maximum number of packages

        Returns:
            List of spack packages
        """
        if not self.spack_executable:
            logger.warning("Spack executable not configured")
            return []

        command = [self.spack_executable, "list"]
        if query:
            command.append(query)

        result = await self._run_command(command)

        if result["exit_code"] != 0:
            logger.error(f"Failed to search packages: {result['stderr']}")
            return []

        packages = []
        lines = result["stdout"].strip().split("\n")[:limit]

        for line in lines:
            package_name = line.strip()
            if package_name:
                package = SpackPackage(
                    name=package_name, version="latest", description=f"Spack package: {package_name}"
                )
                packages.append(package)

        return packages

    async def install_package(
        self,
        package_name: str,
        version: str | None = None,
        variants: list[str] | None = None,
        dependencies: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Install a spack package.

        Args:
            package_name: Package name
            version: Package version
            variants: Package variants
            dependencies: Additional dependencies

        Returns:
            Installation result
        """
        if not self.spack_executable:
            raise ValueError("Spack executable not configured")

        # Build package spec
        spec = package_name
        if version:
            spec += f"@{version}"
        if variants:
            spec += " " + " ".join(variants)
        if dependencies:
            for dep in dependencies:
                spec += f" ^{dep}"

        command = [self.spack_executable, "install", spec]

        logger.info(f"Installing package: {spec}")
        result = await self._run_command(command, timeout=self.settings.command_timeout)

        if result["exit_code"] != 0:
            raise Exception(f"Installation failed: {result['stderr']}")

        return {
            "success": True,
            "package_name": package_name,
            "version": version or "latest",
            "install_path": self._extract_install_path(result["stdout"]),
            "build_log": result["stdout"],
        }

    def _extract_install_path(self, stdout: str) -> str | None:
        """Extract installation path from spack output."""
        # Look for installation path in output
        for line in stdout.split("\n"):
            if "installed" in line.lower() and "/" in line:
                # Simple heuristic to find path-like strings
                words = line.split()
                for word in words:
                    if word.startswith("/") and len(word) > 10:
                        return word
        return None

    async def get_build_info(self, package_name: str, version: str | None = None) -> SpackBuildInfo | None:
        """
        Get build information for a spack package.

        Args:
            package_name: Package name
            version: Package version

        Returns:
            Build information
        """
        if not self.spack_executable:
            logger.warning("Spack executable not configured")
            return None

        spec = package_name
        if version:
            spec += f"@{version}"

        command = [self.spack_executable, "spec", "-I", spec]
        result = await self._run_command(command)

        if result["exit_code"] != 0:
            logger.error(f"Failed to get build info: {result['stderr']}")
            return None

        # Parse spec output
        dependencies = []
        build_system = "unknown"

        for line in result["stdout"].split("\n"):
            if line.strip().startswith("^"):
                # This is a dependency
                dep_name = line.strip().lstrip("^").split("@")[0]
                dependencies.append(dep_name)
            elif "build_system" in line:
                build_system = line.split("=")[-1].strip()

        return SpackBuildInfo(
            package_name=package_name,
            version=version or "latest",
            build_system=build_system,
            dependencies=dependencies,
            build_flags={"spec": spec},
            install_path=None,
        )

    async def uninstall_package(self, package_name: str, version: str | None = None, force: bool = False) -> bool:
        """
        Uninstall a spack package.

        Args:
            package_name: Package name
            version: Package version
            force: Force uninstallation

        Returns:
            True if successful
        """
        if not self.spack_executable:
            raise ValueError("Spack executable not configured")

        spec = package_name
        if version:
            spec += f"@{version}"

        command = [self.spack_executable, "uninstall"]
        if force:
            command.append("--force")
        command.append(spec)

        result = await self._run_command(command)
        return result["exit_code"] == 0

    async def get_package_info(self, package_name: str, version: str | None = None) -> SpackPackage | None:
        """
        Get detailed package information.

        Args:
            package_name: Package name
            version: Package version

        Returns:
            Package information
        """
        if not self.spack_executable:
            logger.warning("Spack executable not configured")
            return None

        command = [self.spack_executable, "info", package_name]
        result = await self._run_command(command)

        if result["exit_code"] != 0:
            logger.error(f"Failed to get package info: {result['stderr']}")
            return None

        # Parse package info
        description = ""
        homepage = ""
        variants = []

        lines = result["stdout"].split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("Description:"):
                description = line.replace("Description:", "").strip()
            elif line.strip().startswith("Homepage:"):
                homepage = line.replace("Homepage:", "").strip()
            elif "variants" in line.lower():
                # Try to extract variants from next few lines
                for j in range(i + 1, min(i + 10, len(lines))):
                    variant_line = lines[j].strip()
                    if variant_line and not variant_line.startswith("Name:"):
                        variants.append(variant_line)
                    elif variant_line.startswith("Name:"):
                        break

        return SpackPackage(
            name=package_name,
            version=version or "latest",
            description=description,
            homepage=homepage,
            variants=variants,
        )

    async def list_compilers(self) -> list[dict[str, Any]]:
        """
        List available compilers.

        Returns:
            List of compiler information
        """
        if not self.spack_executable:
            logger.warning("Spack executable not configured")
            return []

        command = [self.spack_executable, "compiler", "list"]
        result = await self._run_command(command)

        if result["exit_code"] != 0:
            logger.error(f"Failed to list compilers: {result['stderr']}")
            return []

        compilers = []
        current_arch = None

        for line in result["stdout"].split("\n"):
            line = line.strip()
            if line.endswith(":"):
                # This is an architecture line
                current_arch = line.rstrip(":")
            elif line and current_arch:
                # This is a compiler
                compilers.append({"name": line, "architecture": current_arch})

        return compilers
