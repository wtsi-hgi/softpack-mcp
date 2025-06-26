# Softpack MCP Server

A FastAPI-based MCP (Model Context Protocol) server that enables LLMs to interact with spack package building commands. This server is part of the Softpack ecosystem and provides a bridge between language models and the spack package manager.

## Features

- 🚀 **FastAPI Integration**: Modern async/await web framework
- 🔧 **MCP Protocol**: Seamless integration with language models
- 📦 **Spack Commands**: Direct interface to spack package management
- 🐳 **Docker Support**: Containerized deployment
- 📊 **Structured Logging**: Comprehensive logging with rotation
- 🛡️ **Error Handling**: Robust exception handling and validation
- 🔒 **Security**: CORS and authentication support
- 📖 **Auto Documentation**: Interactive API docs with Swagger UI

## MCP Tools Available

The server exposes the following tools to LLMs:

### Spack Package Management
- `search_packages` - Search for available spack packages
- `install_package` - Install a spack package with variants
- `list_packages` - List installed packages
- `package_info` - Get detailed package information
- `build_info` - Get package build information
- `uninstall_package` - Remove installed packages
- `compiler_list` - List available compilers
- `compiler_info` - Get compiler details

## Quick Start

### Prerequisites

- Python 3.8+
- Spack package manager installed
- (Optional) Docker for containerized deployment

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd softpack-mcp
   ```

2. **Install dependencies:**
   ```bash
   pip install -e .
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

### Configuration

Create a `.env` file in the project root:

```env
# Server Settings
SOFTPACK_HOST=127.0.0.1
SOFTPACK_PORT=8000
SOFTPACK_DEBUG=false

# Spack Settings
SOFTPACK_SPACK_EXECUTABLE=spack
SOFTPACK_SPACK_ENV=
SOFTPACK_SPACK_CONFIG_DIR=

# Logging
SOFTPACK_LOG_LEVEL=INFO
SOFTPACK_LOG_FILE=logs/softpack-mcp.log

# Security
SOFTPACK_API_KEY=your-secret-key
SOFTPACK_ALLOWED_ORIGINS=*
```

### Running the Server

#### Development Mode

```bash
# Using the CLI
softpack-mcp serve --host 127.0.0.1 --port 8000 --reload

# Or directly with uvicorn
uvicorn softpack_mcp.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Production Mode

```bash
softpack-mcp serve --host 0.0.0.0 --port 8000
```

#### Docker Deployment

```bash
# Build the image
docker build -t softpack-mcp .

# Run with docker-compose
docker-compose up -d
```

### CLI Commands

The server includes a comprehensive CLI:

```bash
# Start the server
softpack-mcp serve --host 127.0.0.1 --port 8000

# Show configuration
softpack-mcp config

# Check system requirements
softpack-mcp check

# Show version
softpack-mcp version
```

## API Documentation

Once the server is running, visit:

- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json
- **MCP Endpoint**: http://localhost:8000/mcp

## MCP Integration

This server implements the Model Context Protocol (MCP), allowing language models to:

1. **Discover Tools**: Automatically detect available spack commands
2. **Execute Commands**: Run spack operations through structured API calls
3. **Get Results**: Receive formatted responses with error handling
4. **Stream Logs**: Access real-time build logs and progress

### Example MCP Tool Usage

```json
{
  "tool": "install_package",
  "parameters": {
    "package_name": "python",
    "version": "3.11.0",
    "variants": ["+shared", "+optimizations"],
    "dependencies": ["zlib", "openssl"]
  }
}
```

## Development

### Setup Development Environment

```bash
# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=softpack_mcp

# Run specific test file
pytest tests/test_main.py
```

### Code Quality

```bash
# Format code
black softpack_mcp/
isort softpack_mcp/

# Lint code
ruff check softpack_mcp/

# Type checking
mypy softpack_mcp/
```

## Project Structure

```
softpack-mcp/
├── softpack_mcp/           # Main application package
│   ├── __init__.py
│   ├── main.py            # FastAPI application
│   ├── config.py          # Configuration management
│   ├── cli.py             # Command line interface
│   ├── models/            # Pydantic models
│   │   ├── requests.py    # Request models
│   │   └── responses.py   # Response models
│   ├── tools/             # MCP tool implementations
│   │   └── spack.py       # Spack tool endpoints
│   ├── services/          # Business logic layer
│   │   └── spack_service.py # Spack service
│   └── utils/             # Utility modules
│       ├── logging.py     # Logging configuration
│       └── exceptions.py  # Custom exceptions
├── tests/                 # Test suite
├── docs/                  # Documentation
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Container orchestration
├── pyproject.toml        # Project configuration
└── README.md            # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📧 Email: hgi@sanger.ac.uk
- 🐛 Issues: [GitHub Issues](https://github.com/your-org/softpack-mcp/issues)
- 📖 Documentation: [API Docs](http://localhost:8000/docs)

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- MCP integration via [fastapi-mcp](https://github.com/pydantic/fastapi-mcp)
- Spack package manager support
- Part of the Softpack ecosystem

## Development Setup

### Pre-commit Hooks

This project uses `ruff` for code formatting and linting via pre-commit hooks.

#### Installation

The project is configured to work with `uvx` for running pre-commit in an isolated environment:

```bash
# Install pre-commit hooks using uvx (recommended)
uvx pre-commit install

# Run pre-commit on all files
uvx pre-commit run --all-files
```

If `uvx` has issues (e.g., missing sqlite3), you can use the project's virtual environment:

```bash
# Install dependencies including pre-commit
uv sync --dev

# Install pre-commit hooks
uv run pre-commit install

# Run pre-commit on all files
uv run pre-commit run --all-files
```

#### Ruff Configuration

The project uses ruff for:
- Code formatting (replaces black)
- Import sorting (replaces isort)
- Linting (includes pycodestyle, pyflakes, flake8-bugbear, etc.)

Configuration is in `pyproject.toml` under `[tool.ruff]`.

### Logging

This project uses [loguru](https://loguru.readthedocs.io/) for structured logging instead of the standard logging module.

Features:
- Colored console output
- Structured logging with context
- Automatic log rotation
- Exception tracing
- JSON serialization support

#### Usage Examples

```python
from loguru import logger

# Basic logging
logger.info("Server started")
logger.error("Something went wrong")

# Structured logging with context
logger.info("Processing package", package="numpy", version="1.21.0")

# Exception logging with traceback
try:
    some_operation()
except Exception:
    logger.exception("Operation failed")
```

#### Configuration

Logging is configured in `softpack_mcp/utils/logging.py`. The setup includes:
- Console handler with colored output
- File handler with rotation (10MB, 1 month retention)
- Automatic interception of standard library logging

#### Manual Ruff Usage

You can also run ruff directly:

```bash
# Check and fix issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```
