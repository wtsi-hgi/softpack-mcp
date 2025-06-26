"""
Softpack MCP Server

A FastAPI-based Model Context Protocol server for connecting softpack
spack building commands to external services and LLMs.
"""

__version__ = "0.1.0"
__author__ = "Softpack Team"
__email__ = "hgi@sanger.ac.uk"

from .main import app

__all__ = ["app"]
