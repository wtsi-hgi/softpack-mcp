#!/usr/bin/env python3
"""
Example demonstrating session-based isolated spack operations.

This script shows how to create a session and perform spack operations
within that isolated environment.
"""

import asyncio
import json
from typing import Any

import httpx


async def create_session() -> str:
    """Create a new isolated session."""
    async with httpx.AsyncClient() as client:
        response = await client.post("http://localhost:8000/sessions/create")
        result = response.json()
        print(f"✅ Created session: {result['session_id']}")
        print(f"📁 Session directory: {result['session_dir']}")
        print(f"🏷️  Namespace: {result['namespace']}")
        return result["session_id"]


async def search_packages_in_session(session_id: str, query: str = "zlib") -> dict[str, Any]:
    """Search for packages within a specific session."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/spack/search", json={"query": query, "limit": 5, "session_id": session_id}
        )
        result = response.json()
        print(f"🔍 Found {result['total']} packages matching '{query}' in session {session_id}")
        return result


async def install_package_in_session(session_id: str, package_name: str = "zlib"):
    """Install a package within a specific session using streaming."""
    print(f"📦 Installing {package_name} in session {session_id}...")

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/spack/install/stream",
            json={"package_name": package_name, "session_id": session_id},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])  # Remove "data: " prefix
                        event_type = data["type"]
                        message = data["data"]

                        if event_type == "start":
                            print(f"🚀 {message}")
                        elif event_type == "output":
                            print(f"📤 {message}")
                        elif event_type == "error":
                            print(f"❌ {message}")
                        elif event_type == "complete":
                            success = data.get("success", False)
                            if success:
                                print(f"✅ {message}")
                            else:
                                print(f"❌ {message}")
                            break
                    except json.JSONDecodeError:
                        print(f"Failed to parse: {line}")


async def list_sessions() -> dict[str, Any]:
    """List all active sessions."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/sessions/list")
        result = response.json()
        print(f"📋 Active sessions: {len(result)}")
        for session_id, info in result.items():
            print(f"  - {session_id}: {info['namespace']}")
        return result


async def delete_session(session_id: str):
    """Delete a session and clean up its files."""
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"http://localhost:8000/sessions/{session_id}")
        result = response.json()
        print(f"🗑️  {result['message']}")


async def main():
    """Main example workflow."""
    print("🚀 Session Isolation Example")
    print("=" * 50)

    try:
        # Create a new session
        session_id = await create_session()
        print()

        # Search for packages in the session
        await search_packages_in_session(session_id, "zlib")
        print()

        # Note: Package installation would use singularity container
        # which may not be available in development environment
        print("📝 Note: Package installation requires singularity container")
        print("   In production, this would run:")
        print(f"   singularity run --bind /tmp/{session_id}/repos.yaml:/home/ubuntu/.spack/repos.yaml ...")
        print()

        # List all sessions
        await list_sessions()
        print()

        # Clean up
        await delete_session(session_id)

    except Exception as e:
        print(f"❌ Error: {e}")


async def demonstrate_multiple_sessions():
    """Demonstrate multiple isolated sessions."""
    print("\n🔄 Multiple Sessions Example")
    print("=" * 50)

    # Create multiple sessions
    sessions = []
    for _i in range(3):
        session_id = await create_session()
        sessions.append(session_id)

    print(f"\n📊 Created {len(sessions)} isolated sessions")
    await list_sessions()

    # Clean up all sessions
    print("\n🧹 Cleaning up...")
    for session_id in sessions:
        await delete_session(session_id)


if __name__ == "__main__":
    print("Make sure the Softpack MCP server is running:")
    print("  make debug")
    print()

    asyncio.run(main())
    asyncio.run(demonstrate_multiple_sessions())
