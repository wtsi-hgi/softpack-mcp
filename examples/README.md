# Softpack MCP Examples

This directory contains example scripts demonstrating how to use the Softpack MCP server features.

## Streaming Installation Example

The `streaming_client.py` script demonstrates how to use the new streaming spack install endpoint to get real-time installation progress.

### Features

- **Real-time Progress**: See installation progress as it happens
- **Event Types**: Different event types (start, output, error, complete)
- **Timestamps**: Each event includes a timestamp
- **Success Tracking**: Final event indicates installation success/failure

### Usage

1. Start the Softpack MCP server:
   ```bash
   make debug
   ```

2. Run the streaming example:
   ```bash
   python examples/streaming_client.py
   ```

### Example Output

```
🚀 Starting streaming spack installation example...
============================================================
📦 Installing zlib@1.2.13
----------------------------------------
[14:30:07] 🚀 Starting installation of zlib@1.2.13
[14:30:25] 📤 [+] /home/ubuntu/.spack/linux-ubuntu22.04-skylake_avx512/gcc-11.4.0/gmake-4.3-j5qyhpauwffjo3tiy2dxhpazoc6p3v4o
[14:30:25] 📤 ==> Installing zlib-1.2.13-z3btzc5vri4zjz66fo3zdbpi4unve4hd [2/2]
[14:30:25] 📤 ==> No binary for zlib-1.2.13-z3btzc5vri4zjz66fo3zdbpi4unve4hd found: installing from source
[14:30:25] 📤 ==> Fetching https://mirror.spack.io/_source-cache/archive/b3/b3a24de97a8fdbc835b9833169501030b8977031bcb54b3b3ac13740f846ab30.tar.gz
[14:30:25] 📤 ==> No patches needed for zlib
[14:30:26] 📤 ==> zlib: Executing phase: 'edit'
[14:30:26] 📤 ==> zlib: Executing phase: 'build'
[14:30:29] 📤 ==> zlib: Executing phase: 'install'
[14:30:29] 📤 ==> zlib: Successfully installed zlib-1.2.13-z3btzc5vri4zjz66fo3zdbpi4unve4hd
[14:30:29] 📤 ==> Stage: 0.22s. Edit: 0.61s. Build: 2.56s. Install: 0.27s. Post-install: 0.03s. Total: 3.77s
[14:30:29] 📤 [+] /home/ubuntu/.spack/linux-ubuntu22.04-skylake_avx512/gcc-11.4.0/zlib-1.2.13-z3btzc5vri4zjz66fo3zdbpi4unve4hd
[14:30:30] ✅ Successfully installed zlib@1.2.13
⏱️  Total installation time: 23.08 seconds
============================================================
✨ Streaming installation example completed!
```

### API Endpoint

The streaming endpoint is available at:
```
POST /spack/install/stream
```

**Request Body:**
```json
{
  "package_name": "zlib",
  "version": "1.2.13",
  "variants": [],
  "dependencies": []
}
```

**Response:** Server-Sent Events (SSE) stream with JSON data

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

## Copy Package Example

The `copy_package_example.py` script demonstrates how to use the new copy-package endpoint to copy existing spack packages from builtin packages to session directories without using `spack create`.

### Features

- **Legacy Spack Support**: Automatically checks out legacy spack commit `78f95ff38d591cbe956a726f4a93f57d21840f86` before copying packages
- **Direct Copy**: Copies existing packages from builtin packages to session
- **Automatic Modifications**: Applies the same modifications as the shell function
- **Patch Files**: Automatically copies any `.patch` files
- **Session Isolation**: Works within isolated session directories
- **Error Handling**: Proper error handling for missing packages or sessions

### Usage

1. Start the Softpack MCP server:
   ```bash
   make debug
   ```

2. Run the copy package example:
   ```bash
   uv run python examples/copy_package_example.py
   ```

### Example Output

```
🚀 Copy Package Example
==================================================
✅ Created session: 179a2db5-84f0-4b1c-8a6e-dae0534b5890

📦 Copying package: zlib
   ✅ Success: Successfully copied package 'zlib' to session 179a2db5-84f0-4b1c-8a6e-dae0534b5890
   📁 Source: repos/spack_repo/builtin/packages/zlib
   📁 Destination: spack-repo/packages/zlib
   📄 Recipe: spack-repo/packages/zlib/package.py
   🔧 Patches: w_patch.patch, configure-cc.patch
   🔧 Modifications: commented_out_c_cxx_fortran_dependencies, removed_environment_modifications, removed_checked_by_from_licenses, removed_spack_repo_builtin_imports

📦 Copying package: openssl
   ✅ Success: Successfully copied package 'openssl' to session 179a2db5-84f0-4b1c-8a6e-dae0534b5890
   📁 Source: repos/spack_repo/builtin/packages/openssl
   📁 Destination: spack-repo/packages/openssl
   📄 Recipe: spack-repo/packages/openssl/package.py
   🔧 Modifications: commented_out_c_cxx_fortran_dependencies, removed_environment_modifications, removed_checked_by_from_licenses, removed_spack_repo_builtin_imports

📦 Copying package: cmake
   ✅ Success: Successfully copied package 'cmake' to session 179a2db5-84f0-4b1c-8a6e-dae0534b5890
   📁 Source: repos/spack_repo/builtin/packages/cmake
   📁 Destination: spack-repo/packages/cmake
   📄 Recipe: spack-repo/packages/cmake/package.py
   🔧 Patches: intel-c-gnu11.patch, mr-9623.patch, cmake-macos-add-coreservices.patch, pgi-cxx-ansi.patch, nag-response-files.patch, fix-xlf-ninja-mr-4075.patch, ignore_crayxc_warnings.patch, fujitsu_add_linker_option.patch, cmake-revert-findmpi-link-flag-list.patch, intel-cxx-bootstrap.patch, 5882-enable-cce-fortran-preprocessing.patch
   🔧 Modifications: commented_out_c_cxx_fortran_dependencies, removed_environment_modifications, removed_checked_by_from_licenses, removed_spack_repo_builtin_imports

📋 Recipes in session:
   📄 zlib (spack-repo/packages/zlib/package.py)
   📄 openssl (spack-repo/packages/openssl/package.py)
   📄 cmake (spack-repo/packages/cmake/package.py)

✨ Copy package example completed!
Session ID: 179a2db5-84f0-4b1c-8a6e-dae0534b5890
```

### API Endpoint

The copy package endpoint is available at:
```
POST /spack/copy-package
```

**Request Body:**
```json
{
  "package_name": "zlib",
  "session_id": "your-session-id"
}
```

**Response:**
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
    "modifications_applied": [
      "commented_out_c_cxx_fortran_dependencies",
      "removed_environment_modifications",
      "removed_checked_by_from_licenses",
      "removed_spack_repo_builtin_imports"
    ]
  }
}
```

### Modifications Applied

The copy process applies the same modifications as the `create()` function in `.zshrc`:

1. **Comments out build dependencies**: `c`, `cxx`, and `fortran` build dependencies are commented out
2. **Removes environment modifications**: `: EnvironmentModifications` is removed from class definitions
3. **Removes license checked_by**: `checked_by` parameter is removed from license lines
4. **Comments out builtin imports**: Lines starting with `from spack_repo.builtin` are commented out
5. **Legacy spack checkout**: Automatically checks out legacy spack commit before copying

### Benefits

1. **Faster Setup**: No need to run `spack create` for existing packages
2. **Consistent Modifications**: Applies the same modifications as the shell function
3. **Session Isolation**: Works within isolated session directories
4. **Patch Preservation**: Automatically copies patch files
5. **Error Handling**: Proper error handling for missing packages or sessions
