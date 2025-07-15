"""
Session management endpoints.
"""


from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from ..services.session_manager import SessionManager, get_session_manager

router = APIRouter()


@router.post("/create", operation_id="create_session")
async def create_session(
    namespace: str | None = None, session_manager: SessionManager = Depends(get_session_manager)
) -> dict[str, str]:
    """
    Create a new isolated session for recipe building.

    Args:
        namespace: Optional custom namespace for the session's spack repo

    Returns:
        Session information including session_id and details
    """
    try:
        session_id = session_manager.create_session(namespace=namespace)
        session_dir = session_manager.get_session_dir(session_id)

        # Read the actual namespace from the created repo.yaml
        repo_yaml_path = session_dir / "spack-repo" / "repo.yaml"
        actual_namespace = "unknown"
        if repo_yaml_path.exists():
            try:
                content = repo_yaml_path.read_text()
                for line in content.split("\n"):
                    if "namespace:" in line:
                        actual_namespace = line.split("namespace:")[1].strip()
                        break
            except Exception:
                pass

        return {
            "session_id": session_id,
            "session_dir": str(session_dir),
            "namespace": actual_namespace,
            "message": f"Session created successfully with namespace '{actual_namespace}'",
        }
    except Exception as e:
        logger.error("Failed to create session", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/list", operation_id="list_sessions")
async def list_sessions(session_manager: SessionManager = Depends(get_session_manager)) -> dict[str, dict[str, str]]:
    """
    List all active sessions.

    Returns:
        Dictionary of session information
    """
    try:
        sessions = session_manager.list_sessions()
        return sessions
    except Exception as e:
        logger.error("Failed to list sessions", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.get("/{session_id}", operation_id="get_session_info")
async def get_session_info(
    session_id: str, session_manager: SessionManager = Depends(get_session_manager)
) -> dict[str, str]:
    """
    Get information about a specific session.

    Args:
        session_id: Session ID to query

    Returns:
        Session information
    """
    try:
        session_dir = session_manager.get_session_dir(session_id)
        if session_dir is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Read namespace from repo.yaml
        repo_yaml_path = session_dir / "spack-repo" / "repo.yaml"
        namespace = "unknown"
        if repo_yaml_path.exists():
            try:
                content = repo_yaml_path.read_text()
                for line in content.split("\n"):
                    if "namespace:" in line:
                        namespace = line.split("namespace:")[1].strip()
                        break
            except Exception:
                pass

        return {
            "session_id": session_id,
            "session_dir": str(session_dir),
            "namespace": namespace,
            "status": "active" if session_dir.exists() else "inactive",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get session info", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get session info: {str(e)}")


@router.delete("/{session_id}", operation_id="delete_session")
async def delete_session(
    session_id: str, session_manager: SessionManager = Depends(get_session_manager)
) -> dict[str, str]:
    """
    Delete a session and cleanup its files.

    Args:
        session_id: Session ID to delete

    Returns:
        Deletion result
    """
    try:
        success = session_manager.delete_session(session_id)
        if success:
            return {
                "session_id": session_id,
                "status": "deleted",
                "message": f"Session {session_id} deleted successfully",
            }
        else:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found or could not be deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete session", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@router.get("/{session_id}/files", operation_id="list_session_files")
async def list_session_files(
    session_id: str, session_manager: SessionManager = Depends(get_session_manager)
) -> dict[str, list]:
    """
    List files in a session directory.

    Args:
        session_id: Session ID to query

    Returns:
        List of files in the session
    """
    try:
        session_dir = session_manager.get_session_dir(session_id)
        if session_dir is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        files = []
        packages = []

        # List files in session root
        for item in session_dir.iterdir():
            if item.is_file():
                files.append({"name": item.name, "path": str(item.relative_to(session_dir)), "type": "file"})
            elif item.is_dir():
                files.append({"name": item.name, "path": str(item.relative_to(session_dir)), "type": "directory"})

        # List packages in spack-repo/packages
        packages_dir = session_dir / "spack-repo" / "packages"
        if packages_dir.exists():
            for package_dir in packages_dir.iterdir():
                if package_dir.is_dir():
                    packages.append({"name": package_dir.name, "path": str(package_dir.relative_to(session_dir))})

        return {"session_files": files, "packages": packages}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list session files", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list session files: {str(e)}")
