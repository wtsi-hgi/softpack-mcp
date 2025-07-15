#!/usr/bin/env python3
"""
Script to run both the API server and frontend server simultaneously.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully stop both servers."""
    print("\n🛑 Stopping both servers...")
    sys.exit(0)


def main():
    """Run both API and frontend servers."""
    print("🚀 Starting Softpack MCP - API + Frontend")
    print("=" * 50)

    # Check if we're in the right directory
    if not Path("frontend.html").exists():
        print("❌ Error: frontend.html not found. Make sure you're in the project root.")
        sys.exit(1)

    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    print("📋 Starting servers:")
    print("   🔗 API Server: http://localhost:8000")
    print("   🌐 Frontend: http://localhost:8001/frontend.html")
    print("   📖 API Docs: http://localhost:8000/docs")
    print("   ⏹️  Press Ctrl+C to stop both servers")
    print()

    try:
        # Start API server in background
        api_process = subprocess.Popen(
            ["uv", "run", "uvicorn", "softpack_mcp.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
            env={**os.environ, "SOFTPACK_DEBUG": "true"},
        )

        # Give API server a moment to start
        time.sleep(2)

        # Start frontend server
        frontend_process = subprocess.Popen(["python3", "serve_frontend.py"])

        # Wait for both processes
        api_process.wait()
        frontend_process.wait()

    except KeyboardInterrupt:
        print("\n🛑 Stopping servers...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        # Clean up processes
        if "api_process" in locals():
            api_process.terminate()
        if "frontend_process" in locals():
            frontend_process.terminate()
        print("✅ Servers stopped")


if __name__ == "__main__":
    main()
