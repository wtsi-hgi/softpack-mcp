.PHONY: init debug prod clean help frontend both

# Default target
help:
	@echo "Available targets:"
	@echo "  init     - Initialize the project (install dependencies, setup pre-commit)"
	@echo "  debug    - Run the server locally for debugging"
	@echo "  prod     - Run the server in production mode"
	@echo "  frontend - Serve the HTML frontend on port 8001"
	@echo "  both     - Run both API (8000) and frontend (8001) servers"
	@echo "  clean    - Clean cache and temporary files"
	@echo "  help     - Show this help message"

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
		cp .env.example .env; \
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
	@if [ -f .env ]; then export $$(cat .env | xargs); fi && SOFTPACK_DEBUG=true uv run uvicorn softpack_mcp.main:app --host 0.0.0.0 --port 8000 --reload

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

# Serve frontend on port 8001
frontend:
	@echo "🌐 Starting frontend server on port 8001..."
	@echo "📁 Frontend will be available at http://localhost:8001/frontend.html"
	@echo "🔗 API server should be running on http://localhost:8000"
	@echo "⏹️  Press Ctrl+C to stop the server"
	python3 serve_frontend.py

# Run both API and frontend servers
both:
	@echo "🚀 Starting both API and frontend servers..."
	@echo "🔗 API Server: http://localhost:8000"
	@echo "🌐 Frontend: http://localhost:8001/frontend.html"
	@echo "⏹️  Press Ctrl+C to stop both servers"
	python3 run_both.py

svc-install:
	sudo cp softpack-mcp.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable softpack-mcp
	sudo systemctl start softpack-mcp

svc-uninstall:
	sudo systemctl stop softpack-mcp
	sudo systemctl disable softpack-mcp
	sudo rm /etc/systemd/system/softpack-mcp.service
	sudo systemctl daemon-reload

svc-restart:
	sudo systemctl restart softpack-mcp

svc-logs:
	journalctl -u softpack-mcp -f --no-pager
