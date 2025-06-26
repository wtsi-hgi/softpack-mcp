"""
Command line interface for the Softpack MCP Server.
"""

import subprocess
import sys
from pathlib import Path

import typer
import uvicorn
from rich import print
from rich.console import Console
from rich.table import Table

from .config import get_settings

app = typer.Typer(
    name="softpack-mcp",
    help="Softpack MCP Server - FastAPI-based MCP server for spack integration",
    add_completion=False,
)

console = Console()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
    debug: bool = typer.Option(False, help="Enable debug mode"),
) -> None:
    """Start the Softpack MCP server."""
    settings = get_settings()

    # Override settings with CLI arguments
    host = host or settings.host
    port = port or settings.port
    reload = reload or settings.reload
    debug = debug or settings.debug

    print(f"🚀 Starting Softpack MCP Server on http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print(f"🔧 MCP Endpoint: http://{host}:{port}/mcp")

    uvicorn.run(
        "softpack_mcp.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if debug else "info",
    )


@app.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()

    table = Table(title="Softpack MCP Server Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Server settings
    table.add_row("Host", settings.host)
    table.add_row("Port", str(settings.port))
    table.add_row("Debug", str(settings.debug))
    table.add_row("Reload", str(settings.reload))

    # Spack settings
    table.add_row("Spack Executable", settings.spack_executable)
    table.add_row("Spack Environment", settings.spack_env or "None")
    table.add_row("Spack Config Dir", settings.spack_config_dir or "Default")

    # Other settings
    table.add_row("Log Level", settings.log_level)
    table.add_row("Command Timeout", f"{settings.command_timeout}s")
    table.add_row("Max Parallel Jobs", str(settings.max_parallel_jobs))

    console.print(table)


@app.command()
def check() -> None:
    """Check system requirements and configuration."""
    settings = get_settings()
    issues = []

    print("🔍 Checking system requirements...")

    # Check spack
    try:
        result = subprocess.run([settings.spack_executable, "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ Spack found: {version}")
        else:
            issues.append("❌ Spack executable found but failed to get version")
    except FileNotFoundError:
        issues.append(f"❌ Spack executable not found: {settings.spack_executable}")
    except subprocess.TimeoutExpired:
        issues.append("❌ Spack executable timeout")
    except Exception as e:
        issues.append(f"❌ Error checking spack: {e}")

    # Check log directory
    if settings.log_file:
        log_path = Path(settings.log_file)
        if log_path.parent.exists():
            print(f"✅ Log directory accessible: {log_path.parent}")
        else:
            issues.append(f"❌ Log directory not accessible: {log_path.parent}")

    # Summary
    if issues:
        print("\n🚨 Issues found:")
        for issue in issues:
            print(f"  {issue}")
        sys.exit(1)
    else:
        print("\n✅ All checks passed!")


@app.command()
def version() -> None:
    """Show version information."""
    print("Softpack MCP Server v0.1.0")
    print("FastAPI-based MCP server for spack integration")


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
