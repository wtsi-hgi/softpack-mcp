.PHONY: init debug prod clean help frontend both test-integration

# Default target
help:
	@echo "Available targets:"
	@echo "  init     - Initialize the project (install dependencies, setup pre-commit)"
	@echo "  debug    - Run the backend locally for debugging"
	@echo "  backend  - Run backend in foreground on :8000"
	@echo "  backend-start - Run backend in background on :8000"
	@echo "  backend-stop  - Stop background backend process"
	@echo "  prod     - Run backend + dockerized frontend+nginx"
	@echo "  frontend - Run only the frontend via docker compose on port 3000"
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

# Run backend in foreground (production-like)
backend:
	@echo "🔗 Starting backend on http://0.0.0.0:8000"
	@if [ -f .env ]; then export $$(cat .env | grep -E '^SOFTPACK_' | xargs); fi && /home/ubuntu/.local/bin/uv run uvicorn softpack_mcp.main:app --host 0.0.0.0 --port 8000

# Run backend in background
backend-start:
	@echo "🔗 Starting backend in background on http://0.0.0.0:8000"
	@mkdir -p logs
	@if [ -f .env ]; then export $$(cat .env | grep -E '^SOFTPACK_' | xargs); fi; \
		nohup /home/ubuntu/.local/bin/uv run uvicorn softpack_mcp.main:app --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 & echo $$! > logs/backend.pid; \
		echo "✅ Backend PID $$(cat logs/backend.pid)"

backend-stop:
	@echo "🛑 Stopping backend"
	@if [ -f logs/backend.pid ]; then kill $$(cat logs/backend.pid) >/dev/null 2>&1 || true; rm -f logs/backend.pid; else pkill -f "uvicorn softpack_mcp.main:app" >/dev/null 2>&1 || true; fi

# Run production services (backend on host + dockerized frontend + nginx)
prod:
	@echo "🚀 Starting backend + dockerized frontend + nginx..."
	$(MAKE) backend-start
	@echo "   🌐 Frontend: http://0.0.0.0:80 (via nginx)"
	@echo "   🔗 API proxied at /softpack-recipe-creator/api → backend :8000"
	docker compose up -d --build
	@echo "✅ Services up. Use 'docker compose logs -f' to view logs."

down:
	@echo "🛑 Stopping backend"
	$(MAKE) backend-stop
	@echo "🛑 Stopping frontend"
	docker compose down

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

# Serve frontend via docker compose on port 3000 (no nginx)
frontend:
	@echo "🌐 Starting frontend container on port 3000..."
	@echo "📁 Frontend will be available at http://localhost:3000"
	@echo "🔗 API base is controlled by API_BASE_URL in docker-compose.yml"
	SOFTPACK_PORT=8001 /usr/bin/node serve_frontend.js --reload


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
