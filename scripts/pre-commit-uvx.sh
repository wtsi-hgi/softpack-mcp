#!/bin/bash
# Pre-commit script using uvx
# Use this when uvx properly supports sqlite3 in your environment

set -e

echo "Installing pre-commit hooks using uvx..."
uvx pre-commit install

echo "Running pre-commit on all files..."
uvx pre-commit run --all-files

echo "Pre-commit setup complete!"
echo "Future commits will automatically run these checks."
