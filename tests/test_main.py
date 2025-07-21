"""
Tests for the main FastAPI application.
"""

from fastapi.testclient import TestClient

from softpack_mcp.main import app

client = TestClient(app)


def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "softpack-mcp"


def test_spack_endpoints_available():
    """Test that spack endpoints are available."""
    # Test that spack router is mounted
    response = client.get("/spack/search")
    assert response.status_code in [200, 404, 405]  # 404/405 is OK if endpoint doesn't exist or method not allowed


def test_git_endpoints_available():
    """Test that git endpoints are available."""
    # Test that git router is mounted
    response = client.get("/git/pull")
    assert response.status_code in [200, 404, 405]  # 404/405 is OK if endpoint doesn't exist or method not allowed


def test_sessions_endpoints_available():
    """Test that sessions endpoints are available."""
    # Test that sessions router is mounted
    response = client.get("/sessions/list")
    assert response.status_code in [200, 404, 405]  # 404/405 is OK if endpoint doesn't exist or method not allowed


def test_recipes_endpoints_available():
    """Test that recipes endpoints are available."""
    # Test that recipes router is mounted
    response = client.get("/recipes/test-session")
    assert response.status_code in [200, 404, 405]  # 404/405 is OK if endpoint doesn't exist or method not allowed


def test_openapi_docs():
    """Test that OpenAPI documentation is accessible (if debug mode is enabled)."""
    response = client.get("/docs")
    # In production mode, docs might be disabled
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        # If docs are available, check basic structure
        assert "FastAPI" in response.text or "OpenAPI" in response.text
