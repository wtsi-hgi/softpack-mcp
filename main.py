"""
Legacy main.py - redirects to the new package structure.
This file is kept for backward compatibility.
"""

from softpack_mcp.main import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
