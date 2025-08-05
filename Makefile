.PHONY: init debug prod clean help frontend both test-integration

# Default target
help:
	@echo "Available targets:"
	@echo "  init     - Initialize the project (install dependencies, setup pre-commit)"
	@echo "  debug    - Run the server locally for debugging"
	@echo "  prod     - Run the server in production mode"
	@echo "  frontend - Serve the HTML frontend on port 8001"
	@echo "  test-integration - Run the dit package integration test"
	@echo "  clean    - Clean cache and temporary files"
	@echo "  help     - Show this help message"

# Initialize project - install dependencies and setup development environment
init:
	@echo "🚀 Initializing project..."
	@echo "📦 Installing dependencies with uv..."
	/home/ubuntu/.local/bin/uv sync --dev
	@echo "🔧 Setting up pre-commit hooks..."
	/home/ubuntu/.local/bin/uv run pre-commit install
	@echo "🔧 Setting up frontend dependencies with npm..."
	npm install
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
	@if [ -f .env ]; then export $$(cat .env | grep -E '^SOFTPACK_' | xargs); fi && SOFTPACK_DEBUG=true /home/ubuntu/.local/bin/uv run uvicorn softpack_mcp.main:app --host 0.0.0.0 --port 8000 --reload

# Run server in production mode (both backend and frontend)
prod:
	@echo "🚀 Starting Softpack MCP in production mode..."
	@echo "🔗 API Server: http://0.0.0.0:8000"
	@echo "🌐 Frontend: http://0.0.0.0:80"
	@if [ -f .env ]; then export $$(cat .env | xargs); fi && /usr/bin/python3 run_both.py

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
	@echo "📁 Frontend will be available at http://localhost:8001"
	@echo "🔗 API server should be running on http://localhost:8000"
	@echo "⏹️  Press Ctrl+C to stop the server"
	@if [ -f .env ]; then export $$(cat .env | xargs); fi && API_BASE_URL=$${API_BASE_URL:-http://localhost:8000} SOFTPACK_PORT=8001 /usr/bin/node serve_frontend.js


# Run integration test for dit package
test-integration:
	@echo "🧪 Running dit package integration test..."
	@echo "📦 Testing full workflow: session → recipe → copy → build → validate"
	@echo "⏱️  This may take several minutes..."
	/usr/bin/python3 run_integration_test.py

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

svc-stop:
	sudo systemctl stop softpack-mcp

svc-logs:
	journalctl -u softpack-mcp -f --no-pager
