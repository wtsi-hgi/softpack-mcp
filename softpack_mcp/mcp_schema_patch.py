"""
Runtime patch for fastapi_mcp to ensure MCP tool input schemas conform to JSON Schema draft 2020-12.

We hook into fastapi_mcp.openapi.convert.convert_openapi_to_mcp_tools and sanitize the produced
Tool.inputSchema for each tool. This avoids vendoring the library while fixing schema compliance.
"""

from __future__ import annotations

from typing import Any


def _ensure_type_when_inferable(schema: dict[str, Any]) -> None:
    """Add a JSON Schema "type" when it can be inferred.

    - If properties exist and no combinators present, set type to object.
    - If items exist and no combinators present, set type to array.
    - If enum exists and all values share a primitive type, set that type.
    """
    if "type" in schema:
        return

    # Do not override combinators
    if any(k in schema for k in ("anyOf", "oneOf", "allOf", "$ref")):
        return

    if "properties" in schema:
        schema["type"] = "object"
        return

    if "items" in schema:
        schema["type"] = "array"
        return

    # Infer from enum when possible
    enum_vals = schema.get("enum")
    if isinstance(enum_vals, list) and enum_vals:
        value_types = {type(v) for v in enum_vals}
        if len(value_types) == 1:
            py_t = next(iter(value_types))
            mapping = {str: "string", int: "integer", float: "number", bool: "boolean", type(None): "null"}
            if py_t in mapping:
                schema["type"] = mapping[py_t]


def _append_nullability(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a schema that also accepts null based on the given schema.

    - If type is a string, convert to [type, "null"]
    - If type is a list, add "null" if missing
    - Else, append {"type": "null"} to anyOf/oneOf/allOf when present
    - Else, wrap with anyOf: [original, {"type": "null"}]
    """
    if "type" in schema:
        t = schema["type"]
        if isinstance(t, list):
            if "null" not in t:
                schema["type"] = [*t, "null"]
            return schema
        if isinstance(t, str):
            if t != "null":
                schema["type"] = [t, "null"]
            return schema

    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema and isinstance(schema[key], list):
            variants = schema[key]
            # Only add if not already allowing null
            if not any(isinstance(v, dict) and v.get("type") == "null" for v in variants):
                variants.append({"type": "null"})
            return schema

    # Fallback: wrap
    # Make a shallow copy to avoid mutating reference when wrapping
    base = {k: v for k, v in schema.items() if k != "$schema"}
    return {"anyOf": [base, {"type": "null"}]}


def _simplify_anyof_with_null(schema: dict[str, Any]) -> None:
    """Simplify patterns like anyOf: [{type: X}, {type: null}] into type: [X, "null"] when safe.

    Performs in-place simplification for shallow schemas (object, array, string, number, integer, boolean).
    """
    if not isinstance(schema, dict):
        return

    variants = schema.get("anyOf")
    if not isinstance(variants, list) or not variants:
        return

    # Only for the simple case: anyOf of two or more, including a sole {type: null} and one simple {type: T}
    has_null = any(isinstance(v, dict) and v.get("type") == "null" for v in variants)
    non_null_details: list[dict[str, Any]] = []
    for v in variants:
        if isinstance(v, dict) and v.get("type") and v.get("type") != "null":
            # Accept common shapes and preserve key details like items/properties
            non_null_details.append(v)

    if has_null and non_null_details:
        # Merge types
        existing_type = schema.get("type")
        type_set = set()
        if isinstance(existing_type, str):
            type_set.add(existing_type)
        elif isinstance(existing_type, list):
            type_set.update(t for t in existing_type if isinstance(t, str))
        type_set.update(d.get("type") for d in non_null_details if isinstance(d.get("type"), str))
        type_set.add("null")
        schema["type"] = sorted(type_set)

        # Preserve array items if any variant specified it
        if "array" in type_set:
            for d in non_null_details:
                if d.get("type") == "array" and "items" in d and "items" not in schema:
                    schema["items"] = d["items"]
                    break

        # Preserve object properties/required if any variant specified it
        if "object" in type_set:
            for d in non_null_details:
                if d.get("type") == "object":
                    if "properties" in d and "properties" not in schema:
                        schema["properties"] = d["properties"]
                    if "required" in d and "required" not in schema:
                        schema["required"] = d["required"]
                    if "additionalProperties" in d and "additionalProperties" not in schema:
                        schema["additionalProperties"] = d["additionalProperties"]
                    break

        # Remove anyOf entirely since we encoded nullability in type
        schema.pop("anyOf", None)


OPENAPI_ONLY_KEYS = {
    # OpenAPI-specific annotations/keywords that are not part of JSON Schema 2020-12
    "nullable",
    "discriminator",
    "readOnly",
    "writeOnly",
    "xml",
    "externalDocs",
    "example",  # OpenAPI single example
    "examples",  # OpenAPI examples map
    "deprecated",
    "allowReserved",
    "style",
    "explode",
}


def _sanitize_schema_inplace(schema: Any) -> Any:
    """Recursively sanitize an OpenAPI-derived schema into JSON Schema 2020-12.

    - Remove OpenAPI-only keys.
    - Convert nullable: true into JSON Schema nullability.
    - Ensure inferable types are set.
    - Recurse into properties, items, and combinators.
    """
    if not isinstance(schema, dict):
        return schema

    # Handle nullability before removing the flag
    nullable = schema.get("nullable") is True

    # Recurse into known containers first
    if "properties" in schema and isinstance(schema["properties"], dict):
        for prop_name, prop_schema in list(schema["properties"].items()):
            schema["properties"][prop_name] = _sanitize_schema_inplace(prop_schema)

    if "items" in schema:
        schema["items"] = _sanitize_schema_inplace(schema["items"])

    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema and isinstance(schema[key], list):
            schema[key] = [_sanitize_schema_inplace(s) for s in schema[key]]

    if "additionalProperties" in schema and isinstance(schema["additionalProperties"], dict):
        schema["additionalProperties"] = _sanitize_schema_inplace(schema["additionalProperties"])

    # Strip OpenAPI-only keys
    for k in list(schema.keys()):
        if k in OPENAPI_ONLY_KEYS:
            schema.pop(k, None)

    # Set type when we can infer it
    _ensure_type_when_inferable(schema)

    # Apply nullability transformation
    if nullable:
        updated = _append_nullability(schema)
        # _append_nullability may return a wrapped schema; ensure we return that
        schema.clear()
        schema.update(updated)

    # Normalize anyOf with null to a type union when possible
    _simplify_anyof_with_null(schema)

    # Deduplicate required arrays where present
    if isinstance(schema.get("required"), list):
        seen = set()
        deduped = []
        for item in schema["required"]:
            if isinstance(item, str) and item not in seen:
                seen.add(item)
                deduped.append(item)
        schema["required"] = deduped

    return schema


def sanitize_tool_input_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Produce a JSON Schema 2020-12 compliant schema for MCP tool input.

    Adds $schema and sanitizes recursively.
    """
    if not isinstance(schema, dict):
        return schema

    sanitized = _sanitize_schema_inplace(dict(schema))
    # Add the meta-schema identifier for clarity/compliance with strict validators
    sanitized.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
    return sanitized


def apply_fastapi_mcp_schema_patch() -> None:
    """Monkey patch fastapi_mcp's OpenAPI conversion to sanitize tool schemas."""
    try:
        from fastapi_mcp.openapi import convert as _convert_mod  # type: ignore
    except Exception:  # pragma: no cover - if fastapi_mcp isn't installed yet
        return

    # Keep reference to the original
    _orig_convert = _convert_mod.convert_openapi_to_mcp_tools

    def _wrapped_convert(*args, **kwargs) -> tuple[list[Any], dict[str, dict[str, Any]]]:
        tools, operation_map = _orig_convert(*args, **kwargs)

        # Sanitize each tool's inputSchema
        try:
            for tool in tools:
                if getattr(tool, "inputSchema", None):
                    tool.inputSchema = sanitize_tool_input_schema(tool.inputSchema)
        except Exception:
            # Be resilient: if anything goes wrong, fall back to original behavior
            pass

        return tools, operation_map

    # Install the wrapper once (in both the module and any 'from X import' sites we can reach)
    if getattr(_convert_mod, "_softpack_mcp_schema_patch", None) != True:  # noqa: E712
        _convert_mod.convert_openapi_to_mcp_tools = _wrapped_convert  # type: ignore[attr-defined]
        _convert_mod._softpack_mcp_schema_patch = True

        # Also try to update fastapi_mcp.server module symbol that may have been imported as
        # `from fastapi_mcp.openapi.convert import convert_openapi_to_mcp_tools`.
        try:
            import fastapi_mcp.server as _server_mod  # type: ignore

            if getattr(_server_mod, "convert_openapi_to_mcp_tools", None) is not _wrapped_convert:
                _server_mod.convert_openapi_to_mcp_tools = _wrapped_convert
                _server_mod._softpack_mcp_schema_patch = True
        except Exception:
            # If server module is not loaded yet, it's fine.
            pass


# Apply eagerly on import
apply_fastapi_mcp_schema_patch()
