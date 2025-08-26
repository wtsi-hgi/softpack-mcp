# Softpack MCP Server

A comprehensive FastAPI-based MCP (Model Context Protocol) server that enables LLMs and external services to interact with spack package management commands. This server is part of the Softpack ecosystem and provides a complete bridge between language models and the spack package manager, including session management, recipe building, and Git integration.

## Features

- 🚀 **FastAPI Integration**: Modern async/await web framework with automatic API documentation
- 🔧 **MCP Protocol**: Seamless integration with language models via fastapi-mcp
- 📦 **Spack Commands**: Complete interface to spack package management operations
- 🎯 **Session Management**: Isolated workspaces for package development
- 📝 **Recipe Building**: Interactive recipe creation and management
- 🔄 **Git Integration**: Automated Git operations for package workflows
- 📊 **Structured Logging**: Comprehensive logging with rotation and context
- 🛡️ **Error Handling**: Robust exception handling and validation
- 🔒 **Security**: CORS and authentication support
- 📖 **Auto Documentation**: Interactive API docs with Swagger UI
- 🌐 **Web Wizard Interface**: Interactive 6-step wizard for package creation and management

## MCP Tools Available

The server exposes the following comprehensive set of tools to LLMs:

### Spack Package Management
- `search_packages` - Search for available spack packages
- `list_packages` - List installed packages
- `get_package_info` - Get comprehensive package information
- `install_package` - Install a spack package with variants
- `install_package_stream` - Install with real-time streaming output
- `uninstall_package` - Remove installed packages
- `uninstall_package_with_dependents` - Remove package and all dependents
- `copy_existing_package` - Copy existing packages from builtin to session
- `get_package_versions` - Get available versions for a package
- `get_package_checksums` - Get checksums for package versions
- `create_pypi_package` - Create spack package from PyPI
- `create_recipe_from_url` - Create spack package from URL
- `validate_package` - Validate package recipe
- `validate_package_stream` - Validate with real-time streaming

### Session Management
- `create_session` - Create isolated development session
- `list_sessions` - List all active sessions
- `get_session_info` - Get session details
- `delete_session` - Remove session and all contents
- `list_session_files` - List files in session directory

### Recipe Management
- `create_recipe` - Create new package recipe
- `list_recipes` - List all recipes in session
- `read_recipe` - Read recipe content
- `write_recipe` - Write/update recipe content
- `delete_recipe` - Remove recipe
- `validate_recipe` - Validate recipe syntax and content
- `get_recipe_info` - Get recipe metadata

### Git Operations
- `pull_spack_repo` - Pull latest spack-repo updates
- `get_git_commit_info` - Get commit information for repository
- `create_pull_request` - Create pull request for package

### Access Management
- `request_collaborator_access` - Request GitHub collaborator access

## Quick Start

### Prerequisites

- Python 3.10+
- Spack package manager installed
- Git (for repository operations)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd softpack-mcp
   ```

2. **Initialize the project:**
   ```bash
   make init
   ```

This will:
- Install dependencies with uv
- Set up pre-commit hooks
- Create necessary directories
- Create a `.env` file with default values

### Running the Server

#### Development Mode (Backend Only)
```bash
make debug
```

#### Production Mode (Backend + Frontend)
```bash
make prod
```

#### Frontend Only
```bash
make frontend
```

## Configuration

### Environment Variables

The application uses environment variables for configuration. Copy `.env.example` to `.env` and modify as needed:

```bash
cp .env.example .env
```

#### Available Environment Variables

- `SOFTPACK_HOST`: Backend server host (default: `127.0.0.1`)
- `SOFTPACK_PORT`: Backend server port (default: `8000`)
- `SOFTPACK_DEBUG`: Enable debug mode (default: `false`)
- `SOFTPACK_LOG_LEVEL`: Logging level (default: `INFO`)
- `SOFTPACK_SPACK_EXECUTABLE`: Path to spack executable (default: `spack`)
- `SOFTPACK_COMMAND_TIMEOUT`: Command execution timeout in seconds (default: `300`)
- `API_BASE_URL`: Frontend API base URL (default: `http://localhost:8000`)

## API Documentation

Once the server is running, visit:

- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **Web Wizard Interface**: http://localhost:8001

## Web Wizard Interface

The project includes a comprehensive web-based wizard interface (`index.html`) that provides an interactive 6-step workflow for creating and managing spack packages:

### Wizard Steps

1. **Package Information** - Enter package name and type (Python, R, or Other)
2. **Recipe Existence Check** - Automatically check if recipe already exists in spack-repo
3. **Recipe Creation/Version Management** - Create new recipes or manage versions for existing ones
4. **Recipe Modification** - Interactive recipe editor with syntax highlighting and validation
5. **Build and Test** - Install package and run validation tests with real-time output
6. **Create Pull Request** - Prepare Git operations and request collaborator access

### Key Features

- **Interactive Recipe Editor** - Syntax-highlighted editor with real-time validation
- **Real-time Streaming** - Live output for package installation and validation
- **Automatic Recipe Generation** - Support for PyPI packages and existing spack recipes
- **Session Management** - Isolated workspaces for package development
- **Git Integration** - Automated branch creation and pull request preparation
- **Access Management** - Built-in collaborator access request system
- **Progress Tracking** - Visual progress bar and step-by-step guidance

### Accessing the Wizard

The wizard is served on port 8001 and automatically connects to the API server:

```bash
# Start both backend and frontend
make prod

# Or start frontend only (requires backend on port 8000)
make frontend
```

Then visit: http://localhost:8001

## Core Features

### Session Management

The server provides isolated development sessions for package building:

```bash
# Create a new session
curl -X POST "http://localhost:8000/sessions/create" \
  -H "Content-Type: application/json" \
  -d '{"namespace": "my-packages"}'

# List sessions
curl "http://localhost:8000/sessions/list"
```

### Recipe Building

Interactive recipe creation and management within sessions:

```bash
# Create a new recipe
curl -X POST "http://localhost:8000/recipes/{session_id}/{package_name}/create"

# Write recipe content
curl -X PUT "http://localhost:8000/recipes/{session_id}/{package_name}" \
  -H "Content-Type: application/json" \
  -d '{"content": "class MyPackage(Package): ..."}'

# Validate recipe
curl -X POST "http://localhost:8000/recipes/{session_id}/{package_name}/validate" \
  -H "Content-Type: application/json" \
  -d '{"content": "class MyPackage(Package): ..."}'
```

### Streaming Operations

Real-time streaming for long-running operations:

```bash
# Streaming installation
curl -X POST "http://localhost:8000/spack/install/stream" \
  -H "Content-Type: application/json" \
  -d '{"package_name": "zlib", "version": "1.2.13"}' \
  --no-buffer

# Streaming validation
curl -X POST "http://localhost:8000/spack/validate/stream" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "my-session", "package_name": "my-package"}' \
  --no-buffer
```

### Git Integration

Automated Git operations for package workflows:

```bash
# Pull latest spack-repo updates
curl -X POST "http://localhost:8000/git/pull" \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/spack-repo"}'

# Create pull request
curl -X POST "http://localhost:8000/git/pull-request" \
  -H "Content-Type: application/json" \
  -d '{"package_name": "my-package", "session_id": "my-session"}'
```

## Examples

See the `examples/` directory for complete working examples:

- `session_example.py` - Session management workflow
- `recipe_example.py` - Recipe creation and validation
- `copy_package_example.py` - Copying existing packages
- `streaming_client.py` - Streaming installation client

## Development

### Setup Development Environment

```bash
# Initialize the project (installs dependencies and sets up pre-commit)
make init
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=softpack_mcp

# Run integration tests
make test-integration
```

### Code Quality

```bash
# Format and lint code
uv run ruff check . --fix
uv run ruff format .

# Run pre-commit on all files
uv run pre-commit run --all-files
```


## Project Structure

```
softpack-mcp/
├── softpack_mcp/           # Main application package
│   ├── __init__.py
│   ├── main.py            # FastAPI application
│   ├── config.py          # Configuration management
│   ├── repos.yaml         # Spack repository configuration
│   ├── models/            # Pydantic models
│   │   ├── requests.py    # Request models
│   │   └── responses.py   # Response models
│   ├── tools/             # MCP tool implementations
│   │   ├── spack.py       # Spack tool endpoints
│   │   ├── sessions.py    # Session management
│   │   ├── recipes.py     # Recipe management
│   │   ├── git.py         # Git operations
│   │   └── access.py      # Access management
│   ├── services/          # Business logic layer
│   │   ├── spack_service.py # Spack service
│   │   ├── session_manager.py # Session management
│   │   ├── git_service.py # Git operations
│   │   └── access_service.py # Access management
│   └── utils/             # Utility modules
│       ├── logging.py     # Logging configuration
│       └── exceptions.py  # Custom exceptions
├── examples/              # Example scripts and clients
│   ├── session_example.py # Session management example
│   ├── recipe_example.py  # Recipe building example
│   ├── copy_package_example.py # Package copying example
│   ├── streaming_client.py # Streaming client example
│   └── README.md          # Examples documentation
├── tests/                 # Test suite
├── index.html             # Web wizard interface for package creation
├── serve_frontend.py      # Frontend server
├── run_both.py           # Combined server runner
├── Makefile              # Build and run commands
├── pyproject.toml        # Project configuration
└── README.md            # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Run code quality checks (`uv run pre-commit run --all-files`)
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📧 Email: hgi@sanger.ac.uk
- 🐛 Issues: [GitHub Issues](https://github.com/your-org/softpack-mcp/issues)
- 📖 Documentation: [API Docs](http://localhost:8000/docs)

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- MCP integration via [fastapi-mcp](https://github.com/jlowin/fastapi-mcp)
- Spack package manager support
- Part of the Softpack ecosystem
