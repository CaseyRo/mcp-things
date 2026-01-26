"""Core server infrastructure for Things MCP.

This module contains:
- Server factory function
- n8n compatibility middleware
- Schema patching for n8n compatibility
- Shared helper functions
- Server constants
"""

from typing import Dict, Any, Optional, List, Union

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
import mcp.types as types

from .logging_config import get_logger
from .settings import get_settings

logger = get_logger(__name__)

# n8n compatibility: Parameters that n8n's MCP Client Tool incorrectly sends
# See: https://github.com/n8n-io/n8n/issues/21500
N8N_EXTRA_PARAMS = {"toolCallId", "sessionId", "action", "chatInput"}

INSTRUCTIONS_TEXT = (
    "### Things MCP Server - GTD-Native Task Management\n\n"
    "A GTD (Getting Things Done) aligned server for Things 3 on macOS. Tools map to GTD's 5 stages:\n\n"
    "**GTD Workflow Tools**\n"
    "- **Capture**: `capture-task` - Quick inbox capture\n"
    "- **Clarify**: `process-inbox` - Process items with GTD decision tree\n"
    "- **Organize**: `schedule-task`, `delegate-task`, `defer-task`, `plan-project`\n"
    "- **Reflect**: `daily-review`, `weekly-review` - GTD-compliant reviews\n"
    "- **Engage**: `get-tasks`, `focus-mode`, `complete-task` - Context-first task selection\n\n"
    "**GTD Context Tags**\n"
    "Filter tasks by context: @computer, @phone, @office, @home, @errands, @anywhere\n"
    "Use `get-tasks(context='@computer')` to see what you can do at your desk.\n\n"
    "**Waiting For**\n"
    "Use `delegate-task` to track items you're waiting on others to complete.\n\n"
    "**Limitations**\n"
    "- Requires Things 3 for macOS with scripting permissions\n"
    "- Local data only; attachments unavailable\n"
    "- Some operations take a few seconds via URL scheme\n\n"
    "**Support**: https://github.com/CaseyRo/things-fastmcp/issues\n"
)

WEBSITE_URL = "https://github.com/CaseyRo/things-fastmcp"

# Default values for documentation purposes
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8009
HOST_ENV_VAR = "THINGS_FASTMCP_HOST"

# Type alias supporting both newer FastMCP installs (with mcp.types.Icon)
# and older releases that still expect simple dictionaries for icon metadata.
IconLike = Union[Any, Dict[str, Any]]


def _build_icon(
    src: str, *, sizes: Optional[List[str]] = None, mime_type: Optional[str] = None
) -> IconLike:
    """Create an icon instance compatible with the available MCP types module."""
    icon_cls = getattr(types, "Icon", None)
    if icon_cls is not None:
        return icon_cls(src=src, sizes=sizes, mimeType=mime_type)

    # Fall back to a plain dictionary for environments running an older MCP build
    # that predates the Icon model.
    icon_data: Dict[str, Any] = {"src": src}
    if sizes:
        icon_data["sizes"] = sizes
    if mime_type:
        icon_data["mimeType"] = mime_type
    return icon_data


ICONS: List[IconLike] = [
    _build_icon(
        src="https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/72x72/1F4DD.png",
        sizes=["64x64"],
    ),
]


def _error_result(message: str):
    """Raise a ToolError for standardized MCP error handling.

    FastMCP v3 uses ToolError for proper error propagation to clients.
    """
    raise ToolError(message)


def get_binding_host() -> str:
    """Return the host for the FastMCP server from settings."""
    return get_settings().things_fastmcp_host


def get_binding_port() -> int:
    """Return the port for the FastMCP server from settings."""
    return get_settings().things_fastmcp_port


def _flatten_anyof_for_n8n(schema: dict) -> dict:
    """Flatten anyOf constructs in JSON Schema for n8n compatibility.

    n8n's MCP client doesn't handle anyOf properly (causes 'Cannot read properties
    of undefined' errors). This function transforms:
      {"anyOf": [{"type": "string"}, {"type": "null"}]}
    into:
      {"type": ["string", "null"]}

    Using type arrays is valid JSON Schema and allows n8n to accept null values.
    """
    if not isinstance(schema, dict):
        return schema

    result = {}
    for key, value in schema.items():
        if key == "anyOf" and isinstance(value, list):
            # Check if null is one of the options
            has_null = any(t.get("type") == "null" for t in value)
            non_null_types = [t for t in value if t.get("type") != "null"]

            if len(non_null_types) == 1:
                # Simple case: one type + null -> use type array
                flattened = _flatten_anyof_for_n8n(non_null_types[0])
                result.update(flattened)
                # Add null to type if it was in anyOf
                if has_null and "type" in result:
                    current_type = result["type"]
                    if isinstance(current_type, str):
                        result["type"] = [current_type, "null"]
                    elif isinstance(current_type, list) and "null" not in current_type:
                        result["type"] = current_type + ["null"]
            elif len(non_null_types) > 1:
                # Multiple non-null types: pick first, add null if present
                flattened = _flatten_anyof_for_n8n(non_null_types[0])
                result.update(flattened)
                if has_null and "type" in result:
                    current_type = result["type"]
                    if isinstance(current_type, str):
                        result["type"] = [current_type, "null"]
            # If all types are null, skip the anyOf entirely
        elif key == "properties" and isinstance(value, dict):
            # Recurse into properties
            result[key] = {k: _flatten_anyof_for_n8n(v) for k, v in value.items()}
        elif isinstance(value, dict):
            result[key] = _flatten_anyof_for_n8n(value)
        elif isinstance(value, list):
            result[key] = [
                _flatten_anyof_for_n8n(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result


def _patch_tool_serialization_for_n8n(mcp: FastMCP):
    """Patch tool serialization to ensure inputSchema compatibility with n8n.

    n8n's MCP client doesn't handle 'anyOf' constructs in JSON Schema properly,
    causing "Cannot read properties of undefined (reading 'inputType')" errors.

    This patches the low-level request handler for ListToolsRequest to flatten
    anyOf constructs (used by Pydantic for Optional types) before returning
    tools to clients.

    Set THINGS_MCP_DEBUG_SCHEMA=1 to log full tool schemas for debugging.
    """
    import os
    import json
    import mcp.types as mcp_types

    debug_schema = os.environ.get("THINGS_MCP_DEBUG_SCHEMA", "").lower() in (
        "1",
        "true",
        "yes",
    )

    try:
        # Patch the low-level request handler registered with the MCP server
        request_handlers = mcp._mcp_server.request_handlers
        original_handler = request_handlers[mcp_types.ListToolsRequest]

        async def patched_list_tools_handler(request):
            logger.info(
                "ListToolsRequest handler - applying n8n schema compatibility patches"
            )
            result = await original_handler(request)
            # Result is ServerResult with root=ListToolsResult
            tools = result.root.tools
            # Transform each tool's inputSchema to flatten anyOf
            for tool in tools:
                if hasattr(tool, "inputSchema") and tool.inputSchema:
                    if debug_schema:
                        logger.info(
                            f"Tool '{tool.name}' BEFORE flattening: {json.dumps(tool.inputSchema, indent=2)}"
                        )
                    # inputSchema is a dict, flatten it
                    flattened = _flatten_anyof_for_n8n(tool.inputSchema)
                    # Modify the dict in place
                    if isinstance(tool.inputSchema, dict):
                        tool.inputSchema.clear()
                        tool.inputSchema.update(flattened)
                    if debug_schema:
                        logger.info(
                            f"Tool '{tool.name}' AFTER flattening: {json.dumps(tool.inputSchema, indent=2)}"
                        )
            logger.info(f"Processed {len(tools)} tools with schema flattening")
            return result

        request_handlers[mcp_types.ListToolsRequest] = patched_list_tools_handler
        logger.info("Patched ListToolsRequest handler for n8n anyOf compatibility")
    except Exception as e:
        logger.warning(
            f"Could not patch ListToolsRequest handler for n8n compatibility: {e}"
        )

    # Also patch CallToolRequest to strip null values from arguments
    # n8n sends explicit nulls for empty optional fields, but our flattened
    # schema declares them as non-null types
    try:
        original_call_tool = request_handlers[mcp_types.CallToolRequest]

        async def patched_call_tool_handler(request):
            # Strip null values from arguments before validation
            if request.params and request.params.arguments:
                args = request.params.arguments
                null_keys = [k for k, v in args.items() if v is None]
                for key in null_keys:
                    del args[key]
                    logger.debug(f"Stripped null argument '{key}' from tool call")
            return await original_call_tool(request)

        request_handlers[mcp_types.CallToolRequest] = patched_call_tool_handler
        logger.info("Patched CallToolRequest handler for n8n null stripping")
    except Exception as e:
        logger.warning(
            f"Could not patch CallToolRequest handler for n8n compatibility: {e}"
        )


class N8NCompatibilityMiddleware(Middleware):
    """Strip extra parameters and null values that n8n's MCP Client Tool sends."""

    async def on_call_tool(self, context, call_next):
        if hasattr(context, "message") and hasattr(context.message, "arguments"):
            args = context.message.arguments
            if args:
                # Remove n8n-specific parameters that cause Pydantic validation errors
                for param in list(N8N_EXTRA_PARAMS):
                    if param in args:
                        del args[param]
                        logger.debug(f"Stripped n8n parameter '{param}' from tool call")
                # Remove null values - n8n sends explicit nulls for empty optional
                # fields, but our flattened schema declares them as non-null types
                null_params = [k for k, v in args.items() if v is None]
                for param in null_params:
                    del args[param]
                    logger.debug(f"Stripped null parameter '{param}' from tool call")
        return await call_next(context)


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server instance."""
    server = FastMCP(
        "Things",
        instructions=INSTRUCTIONS_TEXT,
        website_url=WEBSITE_URL,
        icons=ICONS,
    )

    # Add n8n compatibility middleware
    # This strips extra parameters that n8n incorrectly sends (toolCallId, sessionId, etc.)
    # See: https://github.com/n8n-io/n8n/issues/21500
    try:
        server.add_middleware(N8NCompatibilityMiddleware())
        logger.info("n8n compatibility middleware registered")
    except Exception as e:
        logger.warning(f"Could not register n8n middleware: {e}")

    return server
