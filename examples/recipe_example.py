#!/usr/bin/env python3
"""
Example demonstrating recipe management functionality.

This script shows how to create, read, write, and validate spack recipes
within isolated sessions.
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


async def create_recipe(session_id: str, package_name: str) -> dict[str, Any]:
    """Create a recipe (copy existing or generate new template)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(f"http://localhost:8000/recipes/{session_id}/{package_name}/create")
        result = response.json()
        print(f"📝 {result['message']}")
        print(f"   Action: {result['details']['action']}")
        if "size" in result["details"]:
            print(f"   Size: {result['details']['size']} bytes")
        return result


async def list_recipes(session_id: str) -> dict[str, Any]:
    """List all recipes in a session."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8000/recipes/{session_id}")
        result = response.json()
        print(f"📋 Found {result['total']} recipes in session:")
        for recipe in result["recipes"]:
            status = "✓" if recipe["exists"] else "✗"
            print(f"   {status} {recipe['package_name']}")
            if recipe["exists"]:
                print(f"     Size: {recipe['size']} bytes")
        return result


async def read_recipe(session_id: str, package_name: str) -> dict[str, Any]:
    """Read a recipe file."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8000/recipes/{session_id}/{package_name}")
        if response.status_code == 404:
            print(f"❌ Recipe for '{package_name}' not found")
            return {}

        result = response.json()
        print(f"📖 Read recipe for '{package_name}':")
        print(f"   Size: {result['size']} bytes")
        print("   Content preview (first 200 chars):")
        print(f"   {result['content'][:200]}...")
        return result


async def write_recipe(session_id: str, package_name: str, content: str) -> dict[str, Any]:
    """Write a recipe file."""
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"http://localhost:8000/recipes/{session_id}/{package_name}",
            json={"content": content, "description": "Modified recipe via API"},
        )
        result = response.json()
        print(f"💾 {result['message']}")
        validation = result["details"]["validation"]
        if validation["warnings"]:
            print(f"   ⚠️  Warnings: {len(validation['warnings'])}")
            for warning in validation["warnings"]:
                print(f"     - {warning}")
        return result


async def validate_recipe(session_id: str, package_name: str, content: str) -> dict[str, Any]:
    """Validate recipe content."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8000/recipes/{session_id}/{package_name}/validate",
            json={"content": content, "package_name": package_name},
        )
        result = response.json()
        status = "✅ Valid" if result["is_valid"] else "❌ Invalid"
        print(f"🔍 Validation result: {status}")
        if result["errors"]:
            print(f"   Errors: {len(result['errors'])}")
            for error in result["errors"]:
                print(f"     - {error}")
        if result["warnings"]:
            print(f"   Warnings: {len(result['warnings'])}")
            for warning in result["warnings"]:
                print(f"     - {warning}")
        return result


async def delete_session(session_id: str):
    """Delete a session."""
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"http://localhost:8000/sessions/{session_id}")
        result = response.json()
        print(f"🗑️  {result['message']}")


async def main():
    """Main example workflow."""
    print("🚀 Recipe Management Example")
    print("=" * 50)

    try:
        # Create a session
        session_id = await create_session()
        print()

        # Try to create a recipe for a common package (zlib)
        print("📝 Creating recipe for 'zlib'...")
        await create_recipe(session_id, "zlib")
        print()

        # List recipes in session
        await list_recipes(session_id)
        print()

        # Read the created recipe
        recipe_content = await read_recipe(session_id, "zlib")
        print()

        if recipe_content:
            # Validate the original content
            print("🔍 Validating original recipe...")
            await validate_recipe(session_id, "zlib", recipe_content["content"])
            print()

            # Modify the recipe (add a comment)
            modified_content = "# Modified recipe\n" + recipe_content["content"]
            print("💾 Writing modified recipe...")
            await write_recipe(session_id, "zlib", modified_content)
            print()

            # Test validation with invalid syntax
            print("🔍 Testing validation with invalid syntax...")
            invalid_content = "this is not valid python syntax {"
            await validate_recipe(session_id, "zlib", invalid_content)
            print()

        # Try to create a recipe for a custom/unknown package
        print("📝 Creating recipe for hypothetical package 'my-custom-tool'...")
        try:
            await create_recipe(session_id, "my-custom-tool")
        except Exception as e:
            print(f"   Note: {e}")
        print()

        # Final recipe listing
        print("📋 Final recipe listing:")
        await list_recipes(session_id)
        print()

        # Clean up
        await delete_session(session_id)

    except Exception as e:
        print(f"❌ Error: {e}")


async def demonstrate_workflow():
    """Demonstrate typical recipe development workflow."""
    print("\n🔄 Recipe Development Workflow")
    print("=" * 50)

    session_id = await create_session()

    try:
        # Step 1: Create initial recipe
        print("Step 1: Create recipe template")
        await create_recipe(session_id, "example-pkg")

        # Step 2: Read and examine
        print("\nStep 2: Read generated template")
        recipe = await read_recipe(session_id, "example-pkg")

        if recipe:
            # Step 3: Validate current state
            print("\nStep 3: Validate template")
            await validate_recipe(session_id, "example-pkg", recipe["content"])

            # Step 4: Make modifications (simulate editing)
            print("\nStep 4: Make modifications")
            modified = recipe["content"].replace(
                'version("main", branch="main")', 'version("1.0.0", sha256="abcd1234")'
            )
            await write_recipe(session_id, "example-pkg", modified)

            # Step 5: Final validation
            print("\nStep 5: Validate modified recipe")
            await validate_recipe(session_id, "example-pkg", modified)

        print("\n✅ Workflow complete!")

    finally:
        await delete_session(session_id)


if __name__ == "__main__":
    print("Make sure the Softpack MCP server is running:")
    print("  make debug")
    print()

    asyncio.run(main())
    asyncio.run(demonstrate_workflow())
