#!/usr/bin/env python3
"""
Example client for the streaming spack install endpoint.

This script demonstrates how to consume the Server-Sent Events (SSE) stream
from the spack install endpoint to get real-time installation progress.
"""

import asyncio
import json
import time
from collections.abc import AsyncGenerator

import httpx


async def stream_spack_install(package_name: str, version: str | None = None) -> AsyncGenerator[dict, None]:
    """
    Stream spack installation progress.

    Args:
        package_name: Name of the package to install
        version: Optional version to install

    Yields:
        Installation progress events
    """
    url = "http://localhost:8000/spack/install/stream"
    payload = {
        "package_name": package_name,
        "version": version,
    }

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])  # Remove "data: " prefix
                        yield data
                    except json.JSONDecodeError:
                        print(f"Failed to parse JSON: {line}")


async def main():
    """Main function demonstrating streaming installation."""
    print("🚀 Starting streaming spack installation example...")
    print("=" * 60)

    # Example: Install a simple package
    package_name = "zlib"
    version = "1.2.13"

    print(f"📦 Installing {package_name}@{version}")
    print("-" * 40)

    start_time = time.time()

    async for event in stream_spack_install(package_name, version):
        event_type = event["type"]
        data = event["data"]
        timestamp = event["timestamp"]

        # Format timestamp
        formatted_time = time.strftime("%H:%M:%S", time.localtime(timestamp))

        if event_type == "start":
            print(f"[{formatted_time}] 🚀 {data}")
        elif event_type == "output":
            print(f"[{formatted_time}] 📤 {data}")
        elif event_type == "error":
            print(f"[{formatted_time}] ❌ {data}")
        elif event_type == "complete":
            success = event.get("success", False)
            if success:
                print(f"[{formatted_time}] ✅ {data}")
            else:
                print(f"[{formatted_time}] ❌ {data}")

            # Calculate total time
            total_time = time.time() - start_time
            print(f"⏱️  Total installation time: {total_time:.2f} seconds")
            break

    print("=" * 60)
    print("✨ Streaming installation example completed!")


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
