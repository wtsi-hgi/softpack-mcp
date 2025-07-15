#!/usr/bin/env python3
"""
Example demonstrating the copy-package endpoint functionality.

This script shows how to copy existing spack packages from builtin packages
to a session without using spack create, similar to the create() function
in .zshrc but skipping the spack create step.
"""

import asyncio
from typing import Any

import httpx


async def create_session() -> str:
    """Create a new isolated session."""
    async with httpx.AsyncClient() as client:
        response = await client.post("http://localhost:8000/sessions/create")
        result = response.json()
        print(f"✅ Created session: {result['session_id']}")
        return result["session_id"]


async def copy_package(session_id: str, package_name: str) -> dict[str, Any]:
    """Copy an existing spack package to the session."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/spack/copy-package", json={"package_name": package_name, "session_id": session_id}
        )
        result = response.json()
        return result


async def list_recipes(session_id: str) -> dict[str, Any]:
    """List recipes in the session."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8000/recipes/{session_id}")
        result = response.json()
        return result


async def main():
    """Main example function."""
    print("🚀 Copy Package Example")
    print("=" * 50)

    # Create a new session
    session_id = await create_session()
    print()

    # Test packages to copy
    test_packages = ["zlib", "openssl", "cmake"]

    for package_name in test_packages:
        print(f"📦 Copying package: {package_name}")
        result = await copy_package(session_id, package_name)

        if result["success"]:
            print(f"   ✅ Success: {result['message']}")
            print(f"   📁 Source: {result['source_path']}")
            print(f"   📁 Destination: {result['destination_path']}")
            print(f"   📄 Recipe: {result['recipe_path']}")

            # Show legacy commit information
            if result.get("copy_details", {}).get("legacy_commit"):
                print(f"   🔄 Legacy Commit: {result['copy_details']['legacy_commit']}")

            # Show patch files if any
            if result.get("copy_details", {}).get("patch_files"):
                print(f"   🔧 Patches: {', '.join(result['copy_details']['patch_files'])}")

            # Show modifications applied
            if result.get("copy_details", {}).get("modifications_applied"):
                print(f"   🔧 Modifications: {', '.join(result['copy_details']['modifications_applied'])}")
        else:
            print(f"   ❌ Failed: {result['message']}")

        print()

    # List all recipes in the session
    print("📋 Recipes in session:")
    recipes_result = await list_recipes(session_id)

    if recipes_result["recipes"]:
        for recipe in recipes_result["recipes"]:
            print(f"   📄 {recipe['package_name']} ({recipe['file_path']})")
    else:
        print("   No recipes found")

    print()
    print("✨ Copy package example completed!")
    print(f"Session ID: {session_id}")


if __name__ == "__main__":
    asyncio.run(main())
