"""
Session manager for handling isolated user sessions.
"""

import uuid
from pathlib import Path

from loguru import logger


class SessionManager:
    """Manages isolated user sessions for recipe building."""

    def __init__(self):
        """Initialize SessionManager."""
        self.sessions: dict[str, Path] = {}
        logger.info("Initialized SessionManager")

    def create_session(self, namespace: str | None = None) -> str:
        """
        Create a new isolated session.

        Args:
            namespace: Optional custom namespace for the session's spack repo

        Returns:
            Session ID (UUID string)
        """
        session_id = str(uuid.uuid4())
        session_dir = Path(f"/tmp/{session_id}")

        logger.info("Creating new session", session_id=session_id, session_dir=str(session_dir))

        try:
            # Create session directory structure
            session_dir.mkdir(exist_ok=True)
            spack_repo_dir = session_dir / "spack-repo"
            packages_dir = session_dir / "packages"

            spack_repo_dir.mkdir(exist_ok=True)
            packages_dir.mkdir(exist_ok=True)

            # Create repos.yaml file
            repos_yaml_content = f"""repos:
- /tmp/{session_id}/spack-repo
- /home/ubuntu/spack-repo
"""
            repos_yaml_path = session_dir / "repos.yaml"
            repos_yaml_path.write_text(repos_yaml_content)

            # Create repo.yaml in spack-repo directory with unique namespace
            if namespace is None:
                namespace = f"session.{session_id[:8]}"

            repo_yaml_content = f"""repo:
  namespace: {namespace}
"""
            repo_yaml_path = spack_repo_dir / "repo.yaml"
            repo_yaml_path.write_text(repo_yaml_content)

            # Create empty packages directory inside spack-repo
            (spack_repo_dir / "packages").mkdir(exist_ok=True)

            # Store session info
            self.sessions[session_id] = session_dir

            logger.success(
                "Session created successfully", session_id=session_id, namespace=namespace, session_dir=str(session_dir)
            )

            return session_id

        except Exception as e:
            logger.error("Failed to create session", session_id=session_id, error=str(e))
            # Cleanup on failure
            if session_dir.exists():
                import shutil

                shutil.rmtree(session_dir, ignore_errors=True)
            raise

    def get_session_dir(self, session_id: str) -> Path | None:
        """
        Get the session directory path for a given session ID.

        Args:
            session_id: Session ID

        Returns:
            Path to session directory or None if session doesn't exist
        """
        if session_id in self.sessions:
            return self.sessions[session_id]

        # Try to recover session from filesystem if it exists
        session_dir = Path(f"/tmp/{session_id}")
        if session_dir.exists() and (session_dir / "repos.yaml").exists():
            self.sessions[session_id] = session_dir
            logger.info("Recovered existing session", session_id=session_id)
            return session_dir

        return None

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and cleanup its files.

        Args:
            session_id: Session ID to delete

        Returns:
            True if session was deleted successfully
        """
        session_dir = self.get_session_dir(session_id)
        if session_dir is None:
            logger.warning("Attempted to delete non-existent session", session_id=session_id)
            return False

        try:
            import shutil

            shutil.rmtree(session_dir, ignore_errors=True)

            # Remove from sessions dict
            if session_id in self.sessions:
                del self.sessions[session_id]

            logger.info("Session deleted successfully", session_id=session_id)
            return True

        except Exception as e:
            logger.error("Failed to delete session", session_id=session_id, error=str(e))
            return False

    def list_sessions(self) -> dict[str, dict[str, str]]:
        """
        List all active sessions.

        Returns:
            Dictionary of session info
        """
        session_info = {}

        for session_id, session_dir in self.sessions.items():
            if session_dir.exists():
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

                session_info[session_id] = {
                    "session_dir": str(session_dir),
                    "namespace": namespace,
                    "created": str(session_dir.stat().st_ctime) if session_dir.exists() else "0",
                }

        return session_info

    def get_singularity_command_prefix(self, session_id: str) -> list[str]:
        """
        Get the singularity command prefix for a session.

        Args:
            session_id: Session ID

        Returns:
            List of command components for singularity execution
        """
        session_dir = self.get_session_dir(session_id)
        if session_dir is None:
            raise ValueError(f"Session {session_id} not found")

        return [
            "singularity",
            "run",
            "--bind",
            "/usr/bin/zsh",
            "--bind",
            "/mnt/data",
            "--bind",
            f"/tmp/{session_id}/repos.yaml:/home/ubuntu/.spack/repos.yaml",
            "--bind",
            f"/tmp/{session_id}/packages:/home/ubuntu/r-spack-recipe-builder/packages",
            "/home/ubuntu/spack.sif",
        ]


# Global session manager instance
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
