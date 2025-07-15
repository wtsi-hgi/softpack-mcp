# Softpack Recipe Manager Frontend

A simple HTML frontend built with Alpine.js for managing spack recipes, installing packages, and creating PyPI recipes.

## Features

- **Session Management**: Create isolated sessions for recipe building
- **Recipe Editor**: Edit, validate, and save spack recipes
- **Package Installation**: Install packages with real-time streaming output
- **PyPI Recipe Creation**: Automatically create spack recipes from PyPI packages
- **Modern UI**: Clean, responsive interface using Tailwind CSS

## Prerequisites

1. **Backend Server**: Make sure the Softpack MCP server is running
   ```bash
   make debug
   ```
   The server should be running on `http://localhost:8000`

2. **Browser**: Modern browser with JavaScript enabled

## Usage

### 1. Start the Backend

First, ensure the Softpack MCP server is running:

```bash
cd softpack-mcp
make debug
```

The server will start on `http://localhost:8000` with API documentation available at `http://localhost:8000/docs`.

### 2. Start the Frontend Server

You have several options to serve the frontend:

#### Option A: Use the Makefile (Recommended)
```bash
# Serve only the frontend on port 8001
make frontend

# OR run both API and frontend simultaneously
make both
```

#### Option B: Use the Python script directly
```bash
# Serve only the frontend
python3 serve_frontend.py

# OR run both servers
python3 run_both.py
```

#### Option C: Manual serving
```bash
# Using Python's built-in server
python3 -m http.server 8001
# Then visit http://localhost:8001/frontend.html
```

### 3. Access the Frontend

Once the frontend server is running, visit:
- **Frontend**: http://localhost:8001/frontend.html
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 3. Create a Session

1. Click "Create New Session" to start an isolated workspace
2. The session ID will be displayed and used for all operations
3. Recipes will be loaded automatically

### 4. Recipe Editor

The **Recipe Editor** tab allows you to:

- **View Recipes**: See all available recipes in your session
- **Create New Recipes**: Generate new recipe templates using spack create
- **Create PyPI Recipes**: Auto-generate recipes from PyPI packages using PyPackageCreator
- **Edit Recipes**: Click on a recipe to load and edit its content
- **Validate Recipes**: Check syntax and validate recipe content
- **Save Recipes**: Save changes back to the session

**Features:**
- Syntax highlighting for Python code
- Real-time validation with error/warning display
- File size and modification time tracking
- Automatic refresh after operations
- Integrated PyPI recipe creation

**Creating Recipes:**
- **New Recipe**: Enter a package name and click "Create Recipe" to generate a template
- **PyPI Recipe**: Enter a PyPI package name (e.g., "requests") and click "Create PyPI Recipe" to auto-generate a spack recipe

### 5. Package Installation

The **Package Installation** tab provides:

- **Install Form**: Specify package name, version, variants, and dependencies
- **Real-time Output**: Stream installation progress as it happens
- **Output Types**: Different colors for different types of output:
  - Green: Start/complete messages
  - Red: Error messages
  - Gray: Standard output

**Example Installation:**
```
Package Name: zlib
Version: 1.2.13
Variants: +shared
Dependencies: (leave empty for none)
```

## API Integration

The frontend integrates with these backend endpoints:

### Session Management
- `POST /sessions/create` - Create new session
- `GET /recipes/{session_id}` - List recipes in session

### Recipe Management
- `GET /recipes/{session_id}/{package_name}` - Read recipe content
- `PUT /recipes/{session_id}/{package_name}` - Save recipe
- `POST /recipes/{session_id}/{package_name}/validate` - Validate recipe

### Package Operations
- `POST /spack/install/stream` - Install package with streaming
- `POST /spack/create-pypi` - Create PyPI recipe

## Troubleshooting

### Common Issues

1. **"Failed to create session"**
   - Ensure the backend server is running on `http://localhost:8000`
   - Check that the server is accessible (try visiting `http://localhost:8000/health`)

2. **"Failed to load recipes"**
   - Make sure you have created a session first
   - Check that the session ID is valid

3. **Installation not starting**
   - Verify the package name is correct
   - Check that the backend has spack properly configured

4. **Streaming output not appearing**
   - Ensure your browser supports Server-Sent Events
   - Check the browser console for JavaScript errors

### Browser Compatibility

The frontend requires:
- Modern browser with ES6+ support
- Fetch API support
- Server-Sent Events support

Tested browsers:
- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

### Development

To modify the frontend:

1. **API Base URL**: Change `apiBase` in the JavaScript to point to your server
2. **Styling**: Modify the Tailwind CSS classes or add custom CSS
3. **Functionality**: Extend the Alpine.js component in the `<script>` section

## Architecture

The frontend uses:

- **Alpine.js**: Reactive JavaScript framework for UI state management
- **Tailwind CSS**: Utility-first CSS framework for styling
- **Fetch API**: Modern JavaScript API for HTTP requests
- **Server-Sent Events**: Real-time streaming for installation output

## Security Notes

- The frontend runs entirely in the browser
- No sensitive data is stored locally
- All operations are performed through the backend API
- Session isolation is handled by the backend

## Contributing

To improve the frontend:

1. **Add Features**: Extend the Alpine.js component with new functionality
2. **Improve UX**: Enhance the UI/UX with better styling and interactions
3. **Error Handling**: Add more robust error handling and user feedback
4. **Accessibility**: Improve accessibility features
5. **Testing**: Add client-side validation and testing

## License

This frontend is part of the Softpack MCP project and follows the same licensing terms.
