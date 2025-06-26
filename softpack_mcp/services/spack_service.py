"""
Spack service for managing spack operations.
"""

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from ..models.responses import OperationResult, SpackBuildInfo, SpackPackage


class SpackService:
    """Service for interacting with Spack package manager."""

    def __init__(self, spack_root: str = "/opt/spack"):
        """
        Initialize Spack service.

        Args:
            spack_root: Path to spack installation
        """
        self.spack_root = Path(spack_root)
        self.spack_cmd = self.spack_root / "bin" / "spack"
        logger.info("Initialized SpackService", spack_root=spack_root)

    async def _run_command(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout: int = 300,
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
        logger.debug("Running command", command=" ".join(command), cwd=str(cwd))

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

    async def search_packages(
        self,
        query: str = "",
        limit: int = 50,
    ) -> list[SpackPackage]:
        """
        Search for spack packages.

        Args:
            query: Search query
            limit: Maximum number of packages

        Returns:
            List of spack packages
        """
        logger.info("Searching packages", query=query, limit=limit)

        cmd = [str(self.spack_cmd), "list"]
        if query:
            cmd.append(query)

        result = await self._run_command(cmd)

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
                        homepage="",
                        variants=[],
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
    ) -> OperationResult:
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
        spec = package_name
        if version:
            spec += f"@{version}"

        if variants:
            for variant in variants:
                spec += f" {variant}"

        logger.info("Installing package", package=spec)

        cmd = [str(self.spack_cmd), "install", spec]

        result = await self._run_command(cmd, timeout=1800)  # 30 minutes timeout

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

    async def get_build_info(
        self,
        package_name: str,
        version: str | None = None,
    ) -> SpackBuildInfo:
        """
        Get build information for a spack package.

        Args:
            package_name: Package name
            version: Package version

        Returns:
            Build information
        """
        spec = package_name
        if version:
            spec += f"@{version}"

        logger.info("Getting build info", package=spec)

        cmd = [str(self.spack_cmd), "info", spec]
        result = await self._run_command(cmd)

        if not result["success"]:
            logger.error("Failed to get build info", package=spec, error=result["stderr"])
            return SpackBuildInfo(
                package_name=package_name,
                version=version or "unknown",
                build_system="unknown",
                dependencies=[],
                build_flags={},
                install_path=None,
            )

        # Parse the info output (simplified)
        lines = result["stdout"].split("\n")
        dependencies = []
        variants = []

        for line in lines:
            line = line.strip()
            if "depends_on" in line:
                dependencies.append(line)
            elif "variant" in line:
                variants.append(line)

        return SpackBuildInfo(
            package_name=package_name,
            version=version or "latest",
            build_system="unknown",
            dependencies=dependencies,
            build_flags={"variants": variants},
            install_path=None,
        )

    async def uninstall_package(
        self,
        package_name: str,
        version: str | None = None,
        force: bool = False,
    ) -> bool:
        """
        Uninstall a spack package.

        Args:
            package_name: Package name
            version: Package version
            force: Force uninstallation

        Returns:
            True if successful
        """
        spec = package_name
        if version:
            spec += f"@{version}"

        logger.info("Uninstalling package", package=spec, force=force)

        cmd = [str(self.spack_cmd), "uninstall"]
        if force:
            cmd.append("--force")
        cmd.append(spec)

        result = await self._run_command(cmd)

        if result["success"]:
            logger.success("Package uninstalled successfully", package=spec)
        else:
            logger.error("Package uninstallation failed", package=spec, error=result["stderr"])

        return result["success"]

    async def get_package_info(
        self,
        package_name: str,
        version: str | None = None,
    ) -> SpackPackage:
        """
        Get detailed package information.

        Args:
            package_name: Package name
            version: Package version

        Returns:
            Package information
        """
        spec = package_name
        if version:
            spec += f"@{version}"

        logger.info("Getting package info", package=spec)

        cmd = [str(self.spack_cmd), "info", spec]
        result = await self._run_command(cmd)

        if not result["success"]:
            logger.error("Failed to get package info", package=spec, error=result["stderr"])
            return SpackPackage(
                name=package_name,
                version=version or "unknown",
                description="Package information unavailable",
                homepage="",
                variants=[],
            )

        # Parse the info output (simplified)
        lines = result["stdout"].split("\n")
        description = ""
        homepage = ""
        dependencies = []
        variants = []

        for line in lines:
            line = line.strip()
            if line.startswith("Description:"):
                description = line.replace("Description:", "").strip()
            elif line.startswith("Homepage:"):
                homepage = line.replace("Homepage:", "").strip()
            elif "depends_on" in line:
                dependencies.append(line)
            elif "variant" in line:
                variants.append(line)

        return SpackPackage(
            name=package_name,
            version=version or "latest",
            description=description or f"Spack package: {package_name}",
            homepage=homepage,
            variants=variants,
        )

    async def list_compilers(self) -> dict[str, Any]:
        """
        List available compilers.

        Returns:
            List of compiler information
        """
        logger.info("Listing compilers")

        cmd = [str(self.spack_cmd), "compiler", "list"]
        result = await self._run_command(cmd)

        if not result["success"]:
            logger.error("Failed to list compilers", error=result["stderr"])
            return {"compilers": [], "error": result["stderr"]}

        # Parse compiler output (simplified)
        compilers = []
        lines = result["stdout"].split("\n")

        for line in lines:
            line = line.strip()
            if line and not line.startswith("=") and not line.startswith("--"):
                compilers.append(line)

        logger.info("Found compilers", count=len(compilers))
        return {"compilers": compilers}


# Global service instance
_spack_service: SpackService | None = None


def get_spack_service() -> SpackService:
    """Get the global spack service instance."""
    global _spack_service
    if _spack_service is None:
        _spack_service = SpackService()
    return _spack_service
