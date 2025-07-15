# Softpack MCP Server

A FastAPI-based MCP (Model Context Protocol) server that enables LLMs to interact with spack package management commands. This server is part of the Softpack ecosystem and provides a bridge between language models and the spack package manager.

## Features

- 🚀 **FastAPI Integration**: Modern async/await web framework
- 🔧 **MCP Protocol**: Seamless integration with language models
- 📦 **Spack Commands**: Direct interface to spack package management
- 📊 **Structured Logging**: Comprehensive logging with rotation
- 🛡️ **Error Handling**: Robust exception handling and validation
- 🔒 **Security**: CORS and authentication support
- 📖 **Auto Documentation**: Interactive API docs with Swagger UI

## MCP Tools Available

The server exposes the following tools to LLMs:

### Spack Package Management
- `search_packages` - Search for available spack packages
- `install_package` - Install a spack package with variants
- `install_package_stream` - **NEW!** Install a spack package with real-time streaming output
- `list_packages` - List installed packages
- `get_package_info` - Get comprehensive package information (includes dependencies, variants, build details)
- `uninstall_package` - Remove installed packages
- `copy_existing_package` - **NEW!** Copy existing spack packages from builtin packages to session without using spack create

## Quick Start

### Prerequisites

- Python 3.8+
- Spack package manager installed

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

#### Development Mode

```bash
make debug
```

#### Production Mode

```bash
make prod
```

## API Documentation

Once the server is running, visit:

- **Interactive API Docs**: http://localhost:8000/docs
- **MCP Endpoint**: http://localhost:8000/mcp

## MCP Integration

This server implements the Model Context Protocol (MCP), allowing language models to:

1. **Discover Tools**: Automatically detect available spack commands
2. **Execute Commands**: Run spack operations through structured API calls
3. **Get Results**: Receive formatted responses with error handling

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

## Streaming Installation

The server now supports **real-time streaming** of spack installation progress using Server-Sent Events (SSE). This allows you to see installation progress as it happens, rather than waiting for completion.

### Streaming Endpoint

```
POST /spack/install/stream
```

### Features

- **Real-time Progress**: See installation output as it happens
- **Event Types**: Different event types (start, output, error, complete)
- **Timestamps**: Each event includes a timestamp
- **Success Tracking**: Final event indicates installation success/failure

### Example Usage

```bash
# Using curl
curl -X POST "http://localhost:8000/spack/install/stream" \
  -H "Content-Type: application/json" \
  -d '{"package_name": "zlib", "version": "1.2.13"}' \
  --no-buffer
```

### Example Client

See `examples/streaming_client.py` for a complete Python client example.

### Event Types

- `start`: Installation started
- `output`: Standard output from spack
- `error`: Error output from spack
- `complete`: Installation completed (with success status)

### Benefits

1. **Real-time Feedback**: No need to wait for completion to see progress
2. **Better UX**: Users can see what's happening during long installations
3. **Debugging**: Easier to identify where installations fail
4. **Monitoring**: Can be used for monitoring and logging systems

## Copy Existing Packages

The server now supports **copying existing spack packages** from builtin packages to session directories without using `spack create`. This functionality mimics the `create()` function from the `.zshrc` file but skips the `spack create` step.

### Copy Package Endpoint

```
POST /spack/copy-package
```

### Features

- **Direct Copy**: Copies existing packages from builtin packages to session
- **Legacy Spack Support**: Automatically checks out legacy spack commit `78f95ff38d591cbe956a726f4a93f57d21840f86` before copying packages
- **Automatic Modifications**: Applies the same modifications as the shell function:
  - Comments out `c`, `cxx`, and `fortran` build dependencies
  - Removes `: EnvironmentModifications` from class definitions
  - Removes `checked_by` from license lines
  - Comments out `from spack_repo.builtin` imports
- **Patch Files**: Automatically copies any `.patch` files
- **Session Isolation**: Works within isolated session directories

### Example Usage

```bash
# Using curl
curl -X POST "http://localhost:8000/spack/copy-package" \
  -H "Content-Type: application/json" \
  -d '{"package_name": "zlib", "session_id": "your-session-id"}'
```

### Example Response

```json
{
  "success": true,
  "message": "Successfully copied package 'zlib' to session your-session-id",
  "package_name": "zlib",
  "source_path": "repos/spack_repo/builtin/packages/zlib",
  "destination_path": "spack-repo/packages/zlib",
  "recipe_path": "spack-repo/packages/zlib/package.py",
  "copy_details": {
    "patch_files": ["w_patch.patch", "configure-cc.patch"],
          "legacy_commit": "78f95ff38d591cbe956a726f4a93f57d21840f86",
      "git_checkout_success": true,
      "modifications_applied": [
        "commented_out_c_cxx_fortran_dependencies",
        "removed_environment_modifications",
        "removed_checked_by_from_licenses",
        "commented_out_spack_repo_builtin_imports"
      ]
  }
}
```

### Example Client

See `examples/copy_package_example.py` for a complete Python client example.

### Benefits

1. **Faster Setup**: No need to run `spack create` for existing packages
2. **Consistent Modifications**: Applies the same modifications as the shell function
3. **Session Isolation**: Works within isolated session directories
4. **Patch Preservation**: Automatically copies patch files
5. **Error Handling**: Proper error handling for missing packages or sessions

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
├── examples/              # Example scripts and clients
│   ├── streaming_client.py # Streaming installation example
│   └── README.md          # Examples documentation
├── tests/                 # Test suite
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
- Spack package manager support
- Part of the Softpack ecosystem

## Development Setup

### Pre-commit Hooks

This project uses `ruff` for code formatting and linting via pre-commit hooks.

```bash
# Initialize the project
make init

# Run pre-commit on all files
uv run pre-commit run --all-files
```

### Ruff Configuration

The project uses ruff for:
- Code formatting (replaces black)
- Import sorting (replaces isort)
- Linting (includes pycodestyle, pyflakes, flake8-bugbear, etc.)

Configuration is in `pyproject.toml` under `[tool.ruff]`.

### Logging

This project uses structured logging with automatic log rotation.

Features:
- Colored console output
- Structured logging with context
- Automatic log rotation
- Exception tracing

### Manual Ruff Usage

You can also run ruff directly:

```bash
# Check and fix issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```
