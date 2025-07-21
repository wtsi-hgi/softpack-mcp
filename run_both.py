#!/usr/bin/env python3
"""
Script to run both the API server and frontend server simultaneously.
"""

import os
import signal
import subprocess
import sys
import time


def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully stop both servers."""
    print("\n🛑 Stopping both servers...")
    sys.exit(0)


def main():
    """Run both API and frontend servers."""
    print("🚀 Starting Softpack MCP - API + Frontend")
    print("=" * 50)

    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    print("📋 Starting servers:")
    print("   🔗 API Server: http://localhost:8000")
    print("   🌐 Frontend: http://localhost:8001")
    print("   ⏹️  Press Ctrl+C to stop both servers")
    print()

    try:
        # Start API server in background (production mode)
        api_process = subprocess.Popen(
            ["uv", "run", "uvicorn", "softpack_mcp.main:app", "--host", "0.0.0.0", "--port", "8000"],
            env=os.environ,
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
