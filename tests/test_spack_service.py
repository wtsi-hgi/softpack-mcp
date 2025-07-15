"""
Tests for the SpackService.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from softpack_mcp.services.spack_service import SpackService


class TestSpackService:
    """Test cases for SpackService."""

    @pytest.fixture
    def spack_service(self):
        """Create a SpackService instance for testing."""
        return SpackService(spack_executable="/usr/bin/spack")

    @pytest.mark.asyncio
    async def test_search_packages_success(self, spack_service):
        """Test successful package search."""
        mock_result = {
            "returncode": 0,
            "stdout": "package1\npackage2\npackage3\n",
            "stderr": "",
            "success": True,
        }

        with patch.object(spack_service, "_run_spack_command", return_value=mock_result):
            packages = await spack_service.search_packages("test")

        assert len(packages) == 3
        assert packages[0].name == "package1"
        assert packages[1].name == "package2"
        assert packages[2].name == "package3"

    @pytest.mark.asyncio
    async def test_search_packages_failure(self, spack_service):
        """Test package search failure."""
        mock_result = {
            "returncode": 1,
            "stdout": "",
            "stderr": "Command failed",
            "success": False,
        }

        with patch.object(spack_service, "_run_spack_command", return_value=mock_result):
            packages = await spack_service.search_packages("test")

        assert packages == []

    @pytest.mark.asyncio
    async def test_install_package_success(self, spack_service):
        """Test successful package installation."""
        mock_result = {
            "returncode": 0,
            "stdout": "Installation completed",
            "stderr": "",
            "success": True,
        }

        with patch.object(spack_service, "_run_spack_command", return_value=mock_result):
            result = await spack_service.install_package("test-package", version="1.0.0")

        assert result.success is True
        assert "Successfully installed test-package@1.0.0" in result.message

    @pytest.mark.asyncio
    async def test_install_package_stream(self, spack_service):
        """Test streaming package installation."""
        # Mock the subprocess creation
        mock_process = AsyncMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                b"Installing package...\n",
                b"Building dependencies...\n",
                b"",  # End of stream
            ]
        )
        mock_process.stderr.readline = AsyncMock(
            side_effect=[
                b"Warning: some warning\n",
                b"",  # End of stream
            ]
        )
        mock_process.wait = AsyncMock(return_value=0)

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            results = []
            async for result in spack_service.install_package_stream("test-package", version="1.0.0"):
                results.append(result)

        # Should have start, output, error, and complete events
        assert len(results) >= 4
        assert results[0].type == "start"
        assert results[0].data == "Starting installation of test-package@1.0.0"
        assert results[-1].type == "complete"
        assert results[-1].success is True

    @pytest.mark.asyncio
    async def test_get_package_info_with_version_only(self, spack_service):
        """Test parsing package info when versions have no URLs."""
        mock_output = """BundlePackage:   dummy-test

Description:
    A dummy bundle package for testing GitHub Actions workflow. Only depends
    on zlib.

Homepage: https://example.com/dummy-test

Preferred version:
    1.0.0

Safe versions:
    1.0.0

Deprecated versions:
    None

Variants:
    build_system [bundle]        bundle
        Build systems supported by the package

Build Dependencies:
    zlib

Link Dependencies:
    None

Run Dependencies:
    zlib

Licenses:
    MIT
"""

        mock_result = {
            "returncode": 0,
            "stdout": mock_output,
            "stderr": "",
            "success": True,
        }

        with patch.object(spack_service, "_run_spack_command", return_value=mock_result):
            package = await spack_service.get_package_info("dummy-test")

        # Test the fix: versions without URLs should be parsed correctly
        assert package.preferred_version is not None
        assert package.preferred_version.version == "1.0.0"
        assert package.preferred_version.url is None

        assert len(package.safe_versions) == 1
        assert package.safe_versions[0].version == "1.0.0"
        assert package.safe_versions[0].url is None

        # Test other parsed fields
        assert package.name == "dummy-test"
        assert package.package_type == "BundlePackage"
        assert "dummy bundle package" in package.description
        assert package.homepage == "https://example.com/dummy-test"
        assert len(package.variants) == 1
        assert package.variants[0].name == "build_system"
        assert package.variants[0].default == "bundle"
        assert package.build_dependencies == ["zlib"]
        assert package.run_dependencies == ["zlib"]
        assert package.licenses == ["MIT"]

    @pytest.mark.asyncio
    async def test_get_package_info_with_version_and_url(self, spack_service):
        """Test parsing package info when versions have URLs."""
        mock_output = """Package:   test-package

Description:
    A test package for testing version parsing.

Homepage: https://example.com/test-package

Preferred version:
    2.1.0    https://github.com/example/test-package/archive/v2.1.0.tar.gz

Safe versions:
    2.1.0    https://github.com/example/test-package/archive/v2.1.0.tar.gz
    2.0.0    https://github.com/example/test-package/archive/v2.0.0.tar.gz

Deprecated versions:
    1.0.0    https://github.com/example/test-package/archive/v1.0.0.tar.gz

Variants:
    None

Build Dependencies:
    None

Link Dependencies:
    None

Run Dependencies:
    None
"""

        mock_result = {
            "returncode": 0,
            "stdout": mock_output,
            "stderr": "",
            "success": True,
        }

        with patch.object(spack_service, "_run_spack_command", return_value=mock_result):
            package = await spack_service.get_package_info("test-package")

        # Test versions with URLs
        assert package.preferred_version is not None
        assert package.preferred_version.version == "2.1.0"
        assert package.preferred_version.url == "https://github.com/example/test-package/archive/v2.1.0.tar.gz"

        assert len(package.safe_versions) == 2
        assert package.safe_versions[0].version == "2.1.0"
        assert package.safe_versions[0].url == "https://github.com/example/test-package/archive/v2.1.0.tar.gz"
        assert package.safe_versions[1].version == "2.0.0"
        assert package.safe_versions[1].url == "https://github.com/example/test-package/archive/v2.0.0.tar.gz"

        assert len(package.deprecated_versions) == 1
        assert package.deprecated_versions[0].version == "1.0.0"
        assert package.deprecated_versions[0].url == "https://github.com/example/test-package/archive/v1.0.0.tar.gz"

    @pytest.mark.asyncio
    async def test_get_package_info_complex_variants(self, spack_service):
        """Test parsing package info with complex variants."""
        mock_output = """PythonPackage:   py-numpy

Description:
    Fundamental package for array computing in Python.

Homepage: https://numpy.org/

Preferred version:
    1.24.3

Safe versions:
    1.24.3
    1.23.5

Variants:
    build_system [python_pip]   python_pip
        Build systems supported by the package

    blas [on]                   on, off
        Enable BLAS support
        when @1.20.0:

    shared [on]                 on, off
        Build shared libraries

Build Dependencies:
    python
    py-setuptools

Link Dependencies:
    blas

Run Dependencies:
    python
    py-setuptools

Licenses:
    BSD-3-Clause
"""

        mock_result = {
            "returncode": 0,
            "stdout": mock_output,
            "stderr": "",
            "success": True,
        }

        with patch.object(spack_service, "_run_spack_command", return_value=mock_result):
            package = await spack_service.get_package_info("py-numpy")

        # Test complex variant parsing
        assert len(package.variants) == 3

        # Test first variant
        build_system_variant = package.variants[0]
        assert build_system_variant.name == "build_system"
        assert build_system_variant.default == "python_pip"

        # Test second variant (with conditional)
        blas_variant = package.variants[1]
        assert blas_variant.name == "blas"
        assert blas_variant.default == "on"
        assert "on" in blas_variant.values or "off" in blas_variant.values

        # Test third variant
        shared_variant = package.variants[2]
        assert shared_variant.name == "shared"
        assert shared_variant.default == "on"

    @pytest.mark.asyncio
    async def test_get_package_info_failure(self, spack_service):
        """Test package info retrieval failure."""
        mock_result = {
            "returncode": 1,
            "stdout": "",
            "stderr": "Package not found",
            "success": False,
        }

        with patch.object(spack_service, "_run_spack_command", return_value=mock_result):
            package = await spack_service.get_package_info("nonexistent-package")

        assert package.name == "nonexistent-package"
        assert package.description == "Package information unavailable"

    @pytest.mark.asyncio
    async def test_uninstall_package_success(self, spack_service):
        """Test successful package uninstallation."""
        mock_result = {
            "returncode": 0,
            "stdout": "Package uninstalled",
            "stderr": "",
            "success": True,
        }

        with patch.object(spack_service, "_run_spack_command", return_value=mock_result):
            result = await spack_service.uninstall_package("test-package")

        assert result is True

    @pytest.mark.asyncio
    async def test_uninstall_package_failure(self, spack_service):
        """Test package uninstallation failure."""
        mock_result = {
            "returncode": 1,
            "stdout": "",
            "stderr": "Package not found",
            "success": False,
        }

        with patch.object(spack_service, "_run_spack_command", return_value=mock_result):
            result = await spack_service.uninstall_package("nonexistent-package")

        assert result is False

    @pytest.mark.asyncio
    async def test_run_command_timeout(self, spack_service):
        """Test command timeout handling."""
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            result = await spack_service._run_command_base(["test", "command"], timeout=1)

        assert result["success"] is False
        assert result["returncode"] == -1
        assert "timed out" in result["stderr"]

    @pytest.mark.asyncio
    async def test_run_command_exception(self, spack_service):
        """Test command execution exception handling."""
        with patch("asyncio.create_subprocess_exec", side_effect=Exception("Test error")):
            result = await spack_service._run_command_base(["test", "command"])

        assert result["success"] is False
        assert result["returncode"] == -1
        assert result["stderr"] == "Test error"
