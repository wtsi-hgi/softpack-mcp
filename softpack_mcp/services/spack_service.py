"""
Spack service for managing spack operations.
"""

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from ..config import get_settings
from ..models.responses import OperationResult, SpackPackage, SpackVariant, SpackVersionInfo


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
        Get comprehensive package information including dependencies and build details.

        Args:
            package_name: Package name
            version: Package version

        Returns:
            Complete package information
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
                        if len(parts) >= 2:
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
                        if len(parts) >= 2:
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
                        if len(parts) >= 2:
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
