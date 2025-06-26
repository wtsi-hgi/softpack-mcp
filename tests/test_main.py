"""
Tests for the main FastAPI application.
"""

from fastapi.testclient import TestClient

from softpack_mcp.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Softpack MCP Server"
    assert data["version"] == "0.1.0"
    assert "docs" in data
    assert "mcp" in data


def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert "services" in data
    assert data["services"]["fastapi"] == "running"
    assert data["services"]["mcp"] == "running"


def test_server_info():
    """Test the server info endpoint."""
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Softpack MCP Server"
    assert data["version"] == "0.1.0"
    assert "description" in data
    assert "features" in data
    assert "endpoints" in data

    # Check that only spack endpoint is listed (no softpack)
    endpoints = data["endpoints"]
    assert "spack" in endpoints
    assert "softpack" not in endpoints


def test_openapi_docs():
    """Test that OpenAPI documentation is accessible."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Softpack MCP Server"
    assert data["info"]["version"] == "0.1.0"
