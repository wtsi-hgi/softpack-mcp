.PHONY: init debug prod clean help

# Default target
help:
	@echo "Available targets:"
	@echo "  init    - Initialize the project (install dependencies, setup pre-commit)"
	@echo "  debug   - Run the server locally for debugging"
	@echo "  prod    - Run the server in production mode"
	@echo "  clean   - Clean cache and temporary files"
	@echo "  help    - Show this help message"

# Initialize project - install dependencies and setup development environment
init:
	@echo "🚀 Initializing project..."
	@echo "📦 Installing dependencies with uv..."
	uv sync --dev
	@echo "🔧 Setting up pre-commit hooks..."
	uv run pre-commit install
	@echo "📁 Creating necessary directories..."
	mkdir -p data logs
	@echo "📄 Creating .env file if it doesn't exist..."
	@if [ ! -f .env ]; then \
		echo "HOST=0.0.0.0" > .env; \
		echo "PORT=8000" >> .env; \
		echo "DEBUG=true" >> .env; \
		echo "LOG_LEVEL=debug" >> .env; \
		echo "✅ Created .env file with default values"; \
	else \
		echo "ℹ️  .env file already exists"; \
	fi
	@echo "✅ Project initialization complete!"

# Run server locally for debugging
debug:
	@echo "🐛 Starting server in debug mode..."
	@echo "🌐 Server will be available at http://localhost:8000"
	@echo "📖 API docs at http://localhost:8000/docs"
	@if [ -f .env ]; then export $$(cat .env | xargs); fi && uv run python main.py

# Run server in production mode
prod:
	@echo "🚀 Starting server in production mode..."
	@echo "🌐 Server will be available at http://0.0.0.0:8000"
	@if [ -f .env ]; then export $$(cat .env | xargs); fi && uv run uvicorn softpack_mcp.main:app --host 0.0.0.0 --port 8000

# Clean cache and temporary files
clean:
	@echo "🧹 Cleaning cache and temporary files..."
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf __pycache__/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	@echo "✅ Cleanup complete!"
