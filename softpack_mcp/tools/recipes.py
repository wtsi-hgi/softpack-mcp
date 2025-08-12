"""
Recipe management endpoints for interactive recipe building.
"""

import ast
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from ..models.requests import RecipeValidateRequest, RecipeWriteRequest
from ..models.responses import (
    OperationResult,
    RecipeContent,
    RecipeInfo,
    RecipeListResult,
    RecipeValidationResult,
)
from ..services.session_manager import SessionManager, get_session_manager

router = APIRouter()


def _get_recipe_path(session_dir: Path, package_name: str) -> Path:
    """Get the path to a recipe file for a package."""
    return session_dir / "spack-repo" / "packages" / package_name / "package.py"


def _ensure_package_directory(recipe_path: Path) -> None:
    """Ensure the package directory exists."""
    recipe_path.parent.mkdir(parents=True, exist_ok=True)


def _validate_package_name(package_name: str) -> None:
    """Validate package name format."""
    if not package_name:
        raise HTTPException(status_code=400, detail="Package name cannot be empty")


def _validate_python_syntax(content: str) -> tuple[bool, list[str]]:
    """Validate Python syntax of recipe content."""
    errors = []
    try:
        ast.parse(content)
        return True, []
    except SyntaxError as e:
        errors.append(f"Syntax error on line {e.lineno}: {e.msg}")
        return False, errors
    except Exception as e:
        errors.append(f"Parse error: {str(e)}")
        return False, errors


def _validate_recipe_content(content: str, package_name: str) -> RecipeValidationResult:
    """Validate recipe content for common issues."""
    errors = []
    warnings = []

    # Check Python syntax first
    syntax_valid, syntax_errors = _validate_python_syntax(content)
    errors.extend(syntax_errors)

    if syntax_valid:
        try:
            # Parse the AST to check for required elements
            tree = ast.parse(content)

            # Check for class definition
            class_found = False
            matching_class_found = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_found = True
                    # Check if class name matches package name pattern
                    # Convert package-name to PackageName (PascalCase, no hyphens/underscores)
                    parts = package_name.replace("-", "_").replace(".", "_").split("_")
                    expected_class = "".join(part.capitalize() for part in parts if part)
                    if node.name.lower() == expected_class.lower():
                        matching_class_found = True
                    else:
                        # Only warn about non-matching classes if we haven't found a matching one yet
                        if not matching_class_found:
                            warnings.append(
                                f"Class name '{node.name}' doesn't match expected pattern '{expected_class}'"
                            )

            if not class_found:
                errors.append("No package class definition found")
            elif not matching_class_found:
                warnings.append(f"No class found matching expected package name pattern '{expected_class}'")

            # Check for common required methods/attributes (basic validation)
            content_lower = content.lower()
            if "homepage" not in content_lower:
                warnings.append("No homepage attribute found")
            if "url" not in content_lower and "git" not in content_lower:
                warnings.append("No URL or Git repository found")
            if "version(" not in content_lower:
                warnings.append("No version definitions found")

        except Exception as e:
            warnings.append(f"Advanced validation failed: {str(e)}")

    is_valid = len(errors) == 0

    return RecipeValidationResult(
        package_name=package_name,
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        syntax_valid=syntax_valid,
    )


@router.post("/{session_id}/{package_name}/create", response_model=OperationResult, operation_id="create_recipe")
async def create_recipe(
    session_id: str,
    package_name: str,
    session_manager: SessionManager = Depends(get_session_manager),
) -> OperationResult:
    """
    Create or copy a recipe for a package.

    If the recipe exists in ~/spack-repo, it copies it to the session.
    If not, it uses 'spack create' to generate a new template.

    Args:
        session_id: Session ID
        package_name: Package name to create recipe for

    Returns:
        Operation result with details about the created recipe
    """
    try:
        _validate_package_name(package_name)

        session_dir = session_manager.get_session_dir(session_id)
        if session_dir is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Check if recipe already exists in session
        session_recipe_path = _get_recipe_path(session_dir, package_name)
        if session_recipe_path.exists():
            return OperationResult(
                success=True,
                message=f"Recipe for '{package_name}' already exists in session",
                details={
                    "package_name": package_name,
                    "action": "exists",
                    "file_path": str(session_recipe_path.relative_to(session_dir)),
                },
            )

        # Check if recipe exists in global spack repo
        global_recipe_path = Path("/home/ubuntu/spack-repo/packages") / package_name / "package.py"
        global_package_dir = Path("/home/ubuntu/spack-repo/packages") / package_name

        if global_recipe_path.exists():
            # Copy entire package directory from global repo
            session_package_dir = session_recipe_path.parent
            _ensure_package_directory(session_recipe_path)

            # Remove existing package directory if it exists
            if session_package_dir.exists():
                shutil.rmtree(session_package_dir)

            # Copy the entire package directory
            shutil.copytree(global_package_dir, session_package_dir)

            # Get list of copied files for logging
            copied_files = []
            if session_package_dir.exists():
                copied_files = [f.name for f in session_package_dir.iterdir() if f.is_file()]

            # Check for patch files
            patch_files = [f for f in copied_files if f.endswith(".patch")]

            logger.success(
                "Copied package from global repo",
                session_id=session_id,
                package_name=package_name,
                source=str(global_package_dir),
                copied_files=copied_files,
                patch_files=patch_files,
            )

            return OperationResult(
                success=True,
                message=f"Copied existing package '{package_name}' from global repository",
                details={
                    "package_name": package_name,
                    "action": "copied",
                    "source": str(global_package_dir),
                    "destination": str(session_package_dir.relative_to(session_dir)),
                    "copied_files": copied_files,
                    "patch_files": patch_files,
                    "size": session_recipe_path.stat().st_size if session_recipe_path.exists() else 0,
                },
            )

        else:
            # Generate new recipe using spack create
            logger.info("Generating new recipe", session_id=session_id, package_name=package_name)

            # Import here to avoid circular imports
            from ..services.spack_service import get_spack_service

            spack_service = get_spack_service()

            # Run spack create with session context (skip editor for non-interactive mode)
            create_cmd = [str(spack_service.spack_cmd), "create", "--skip-editor", package_name]
            result = await spack_service._run_spack_command(create_cmd, session_id=session_id, timeout=120)

            if not result["success"]:
                logger.error(
                    "Spack create failed", session_id=session_id, package_name=package_name, error=result["stderr"]
                )
                raise HTTPException(status_code=500, detail=f"Failed to generate recipe: {result['stderr']}")

            # After spack create, search for all package.py files in the session's spack-repo/packages directory
            import re

            package_py_files = list((session_dir / "spack-repo" / "packages").rglob("package.py"))
            found_main_recipe = None
            # Improved regex: match any dashed block anywhere in the file
            pattern = r"(?ms)^# -{10,}\n(?:.*?\n)*?# -{10,}(?:\n|$)"
            for pyfile in package_py_files:
                content = pyfile.read_text(encoding="utf-8")
                logger.debug(f"Before removal ({pyfile}):\n{content[:200]}")
                content_cleaned, n = re.subn(pattern, "", content)
                logger.debug(f"After removal ({pyfile}):\n{content_cleaned[:200]}")
                if n > 0:
                    logger.info(f"Removed {n} Spack boilerplate dashed block(s) from {pyfile}")
                pyfile.write_text(content_cleaned, encoding="utf-8")
                if pyfile == session_recipe_path:
                    found_main_recipe = pyfile

            # If the main recipe was not found, try to find it among discovered files
            if not found_main_recipe and package_py_files:
                found_main_recipe = package_py_files[0]

            if found_main_recipe:
                logger.success(
                    "Generated recipe and removed boilerplate", session_id=session_id, package_name=package_name
                )
                action = "generated_and_cleaned"
                file_path = str(found_main_recipe.relative_to(session_dir))
                size = found_main_recipe.stat().st_size
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Recipe generation succeeded but no recipe file found for '{package_name}'",
                )

            return OperationResult(
                success=True,
                message=f"Generated new recipe for '{package_name}' using spack create",
                details={
                    "package_name": package_name,
                    "action": action,
                    "file_path": file_path,
                    "size": size,
                    "spack_output": result["stdout"],
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create recipe", session_id=session_id, package_name=package_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create recipe: {str(e)}")


@router.get("/{session_id}", response_model=RecipeListResult, operation_id="list_recipes")
async def list_recipes(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
) -> RecipeListResult:
    """
    List all recipe files in a session.

    Args:
        session_id: Session ID to list recipes from

    Returns:
        List of recipe files with metadata
    """
    try:
        session_dir = session_manager.get_session_dir(session_id)
        if session_dir is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        packages_dir = session_dir / "spack-repo" / "packages"
        recipes = []

        if packages_dir.exists():
            for package_dir in packages_dir.iterdir():
                if package_dir.is_dir():
                    recipe_file = package_dir / "package.py"
                    if recipe_file.exists():
                        stat = recipe_file.stat()
                        recipes.append(
                            RecipeInfo(
                                package_name=package_dir.name,
                                file_path=f"spack-repo/packages/{package_dir.name}/package.py",
                                exists=True,
                                size=stat.st_size,
                                modified=stat.st_mtime,
                            )
                        )
                    else:
                        # Package directory exists but no recipe file
                        recipes.append(
                            RecipeInfo(
                                package_name=package_dir.name,
                                file_path=f"spack-repo/packages/{package_dir.name}/package.py",
                                exists=False,
                                size=None,
                                modified=None,
                            )
                        )

        logger.info("Listed recipes", session_id=session_id, count=len(recipes))
        return RecipeListResult(
            session_id=session_id,
            recipes=recipes,
            total=len(recipes),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list recipes", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list recipes: {str(e)}")


@router.get("/{session_id}/{package_name}", response_model=RecipeContent, operation_id="read_recipe")
async def read_recipe(
    session_id: str,
    package_name: str,
    session_manager: SessionManager = Depends(get_session_manager),
) -> RecipeContent:
    """
    Read a recipe file from a session.

    Args:
        session_id: Session ID
        package_name: Package name

    Returns:
        Recipe file content and metadata
    """
    try:
        _validate_package_name(package_name)

        session_dir = session_manager.get_session_dir(session_id)
        if session_dir is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        recipe_path = _get_recipe_path(session_dir, package_name)

        if not recipe_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Recipe for package '{package_name}' not found in session {session_id}"
            )

        content = recipe_path.read_text(encoding="utf-8")
        stat = recipe_path.stat()

        logger.info("Read recipe", session_id=session_id, package_name=package_name, size=len(content))

        return RecipeContent(
            package_name=package_name,
            content=content,
            file_path=f"spack-repo/packages/{package_name}/package.py",
            size=stat.st_size,
            modified=stat.st_mtime,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to read recipe", session_id=session_id, package_name=package_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to read recipe: {str(e)}")


@router.put("/{session_id}/{package_name}", response_model=OperationResult, operation_id="write_recipe")
async def write_recipe(
    session_id: str,
    package_name: str,
    request: RecipeWriteRequest,
    session_manager: SessionManager = Depends(get_session_manager),
) -> OperationResult:
    """
    Write a recipe file to a session.

    Args:
        session_id: Session ID
        package_name: Package name
        request: Recipe content and metadata

    Returns:
        Operation result
    """
    try:
        _validate_package_name(package_name)

        session_dir = session_manager.get_session_dir(session_id)
        if session_dir is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        recipe_path = _get_recipe_path(session_dir, package_name)

        # Ensure package directory exists
        _ensure_package_directory(recipe_path)

        # Validate content before writing
        validation = _validate_recipe_content(request.content, package_name)
        if not validation.syntax_valid:
            raise HTTPException(status_code=400, detail=f"Invalid Python syntax: {', '.join(validation.errors)}")

        # Write the file
        recipe_path.write_text(request.content, encoding="utf-8")

        logger.success(
            "Wrote recipe",
            session_id=session_id,
            package_name=package_name,
            size=len(request.content),
            warnings=len(validation.warnings),
        )

        details = {
            "package_name": package_name,
            "file_path": str(recipe_path.relative_to(session_dir)),
            "size": len(request.content),
            "validation": validation.model_dump(),
        }

        if request.description:
            details["description"] = request.description

        return OperationResult(
            success=True,
            message=f"Successfully wrote recipe for package '{package_name}'",
            details=details,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to write recipe", session_id=session_id, package_name=package_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to write recipe: {str(e)}")


@router.delete("/{session_id}/{package_name}", response_model=OperationResult, operation_id="delete_recipe")
async def delete_recipe(
    session_id: str,
    package_name: str,
    session_manager: SessionManager = Depends(get_session_manager),
) -> OperationResult:
    """
    Delete a recipe directory from a session.

    Args:
        session_id: Session ID
        package_name: Package name

    Returns:
        Operation result
    """
    try:
        _validate_package_name(package_name)

        session_dir = session_manager.get_session_dir(session_id)
        if session_dir is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        recipe_path = _get_recipe_path(session_dir, package_name)

        package_dir = recipe_path.parent

        # If neither the recipe file nor the package directory exists, return 404
        if not (recipe_path.exists() or package_dir.exists()):
            raise HTTPException(
                status_code=404, detail=f"Recipe for package '{package_name}' not found in session {session_id}"
            )

        # Always remove the entire package directory to ensure patch files and other assets are removed
        if package_dir.exists():
            shutil.rmtree(package_dir, ignore_errors=False)
        elif recipe_path.exists():
            # Fallback: in the unlikely event the directory is missing but file exists
            recipe_path.unlink()

        logger.info("Deleted recipe", session_id=session_id, package_name=package_name)

        return OperationResult(
            success=True,
            message=f"Successfully deleted recipe directory for package '{package_name}'",
            details={
                "package_name": package_name,
                "file_path": f"spack-repo/packages/{package_name}/package.py",
                "deleted_dir": f"spack-repo/packages/{package_name}",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete recipe", session_id=session_id, package_name=package_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete recipe: {str(e)}")


@router.post(
    "/{session_id}/{package_name}/validate", response_model=RecipeValidationResult, operation_id="validate_recipe"
)
async def validate_recipe(
    session_id: str,
    package_name: str,
    request: RecipeValidateRequest,
    session_manager: SessionManager = Depends(get_session_manager),
) -> RecipeValidationResult:
    """
    Validate recipe content without writing to file.

    Args:
        session_id: Session ID
        package_name: Package name
        request: Recipe validation request

    Returns:
        Validation result with errors and warnings
    """
    try:
        _validate_package_name(package_name)

        session_dir = session_manager.get_session_dir(session_id)
        if session_dir is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Validate the content
        validation_result = _validate_recipe_content(request.content, request.package_name)

        logger.info(
            "Validated recipe",
            session_id=session_id,
            package_name=package_name,
            is_valid=validation_result.is_valid,
            errors=len(validation_result.errors),
            warnings=len(validation_result.warnings),
        )

        return validation_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to validate recipe", session_id=session_id, package_name=package_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to validate recipe: {str(e)}")


@router.get("/{session_id}/{package_name}/info", response_model=RecipeInfo, operation_id="get_recipe_info")
async def get_recipe_info(
    session_id: str,
    package_name: str,
    session_manager: SessionManager = Depends(get_session_manager),
) -> RecipeInfo:
    """
    Get metadata about a recipe file without reading its content.

    Args:
        session_id: Session ID
        package_name: Package name

    Returns:
        Recipe file metadata
    """
    try:
        _validate_package_name(package_name)

        session_dir = session_manager.get_session_dir(session_id)
        if session_dir is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        recipe_path = _get_recipe_path(session_dir, package_name)

        if recipe_path.exists():
            stat = recipe_path.stat()
            recipe_info = RecipeInfo(
                package_name=package_name,
                file_path=f"spack-repo/packages/{package_name}/package.py",
                exists=True,
                size=stat.st_size,
                modified=stat.st_mtime,
            )
        else:
            recipe_info = RecipeInfo(
                package_name=package_name,
                file_path=f"spack-repo/packages/{package_name}/package.py",
                exists=False,
                size=None,
                modified=None,
            )

        logger.info("Got recipe info", session_id=session_id, package_name=package_name, exists=recipe_info.exists)
        return recipe_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get recipe info", session_id=session_id, package_name=package_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get recipe info: {str(e)}")
