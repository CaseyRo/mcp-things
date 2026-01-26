"""Core server infrastructure for Things MCP.

This module contains:
- Server factory function
- Client compatibility middleware (n8n, ChatGPT)
- Schema patching for client compatibility
- Shared helper functions
- Server constants
- Server statistics tracking
"""

import time
from collections import defaultdict
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

# GTD quotes for shutdown messages
GTD_QUOTES = [
    "Your mind is for having ideas, not holding them. - David Allen",
    "You can do anything, but not everything. - David Allen",
    "The secret of getting ahead is getting started. - Mark Twain",
    "Mind like water. - GTD Principle",
    "What's the next action? - The GTD question",
    "If it takes less than 2 minutes, do it now. - GTD Rule",
    "Review weekly, or things will slip through the cracks. - GTD Wisdom",
    "Your inbox is not your to-do list. - GTD Truth",
    "Done is better than perfect. - Sheryl Sandberg",
    "The two-minute rule: Just do it. - GTD",
]


class ServerStats:
    """Track server statistics for shutdown summary."""

    def __init__(self):
        self.start_time: float = time.time()
        self.tool_calls: Dict[str, int] = defaultdict(int)
        self.total_calls: int = 0
        self.errors: int = 0

    def record_tool_call(self, tool_name: str, success: bool = True):
        """Record a tool call."""
        self.tool_calls[tool_name] += 1
        self.total_calls += 1
        if not success:
            self.errors += 1

    def get_uptime(self) -> str:
        """Get human-readable uptime."""
        elapsed = time.time() - self.start_time
        if elapsed < 60:
            return f"{elapsed:.0f}s"
        elif elapsed < 3600:
            minutes = elapsed / 60
            return f"{minutes:.1f}m"
        else:
            hours = elapsed / 3600
            return f"{hours:.1f}h"

    def get_summary(self) -> Dict[str, Any]:
        """Get statistics summary."""
        top_tools = sorted(self.tool_calls.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]
        return {
            "uptime": self.get_uptime(),
            "total_calls": self.total_calls,
            "unique_tools": len(self.tool_calls),
            "errors": self.errors,
            "top_tools": top_tools,
        }


# Global server stats instance
server_stats = ServerStats()

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


def _add_additional_properties_false(schema: dict) -> dict:
    """Add additionalProperties: false to all object schemas for ChatGPT compatibility.

    ChatGPT's strict mode requires additionalProperties: false on every object.
    This recursively adds the property to all objects in the schema.

    See: https://github.com/github/github-mcp-server/issues/376
    """
    if not isinstance(schema, dict):
        return schema

    result = dict(schema)

    # If this is an object with properties, add additionalProperties: false
    if result.get("type") == "object" or "properties" in result:
        if "additionalProperties" not in result:
            result["additionalProperties"] = False

    # Recurse into properties
    if "properties" in result:
        result["properties"] = {
            k: _add_additional_properties_false(v)
            for k, v in result["properties"].items()
        }

    # Recurse into items (for arrays)
    if "items" in result and isinstance(result["items"], dict):
        result["items"] = _add_additional_properties_false(result["items"])

    # Recurse into nested schemas in other locations
    for key in ["allOf", "oneOf", "anyOf"]:
        if key in result and isinstance(result[key], list):
            result[key] = [
                _add_additional_properties_false(item)
                if isinstance(item, dict)
                else item
                for item in result[key]
            ]

    return result


def _make_all_fields_required(schema: dict) -> dict:
    """Make all fields required with nullable types for ChatGPT compatibility.

    ChatGPT's strict mode requires ALL properties to be listed in the required array.
    Optional fields should use type arrays like ["string", "null"] instead of being
    omitted from required.

    See: https://community.openai.com/t/strict-true-and-required-fields/1131075
    """
    if not isinstance(schema, dict):
        return schema

    result = dict(schema)

    if "properties" in result:
        all_props = list(result["properties"].keys())
        current_required = set(result.get("required", []))

        # For fields not currently required, make them nullable
        new_properties = {}
        for prop_name, prop_schema in result["properties"].items():
            # Recurse first
            prop_schema = _make_all_fields_required(dict(prop_schema))

            if prop_name not in current_required:
                # Add null to type for optional fields
                if "type" in prop_schema:
                    current_type = prop_schema["type"]
                    if isinstance(current_type, str) and current_type != "null":
                        prop_schema["type"] = [current_type, "null"]
                    elif isinstance(current_type, list) and "null" not in current_type:
                        prop_schema["type"] = current_type + ["null"]
                elif "type" not in prop_schema:
                    # No type specified, add nullable type
                    prop_schema["type"] = ["object", "null"]

            new_properties[prop_name] = prop_schema

        result["properties"] = new_properties
        result["required"] = all_props

    # Recurse into items (for arrays of objects)
    if "items" in result and isinstance(result["items"], dict):
        result["items"] = _make_all_fields_required(result["items"])

    return result


def _patch_tool_serialization(mcp: FastMCP):
    """Patch tool serialization for n8n and ChatGPT compatibility.

    Applies schema transformations to make tools work with both:
    - n8n: Needs anyOf flattened (can't parse anyOf constructs)
    - ChatGPT: Needs additionalProperties:false and all fields in required

    ChatGPT's requirements are a superset of n8n's, so we apply all transformations
    to all requests. This "just works" for both clients without configuration.

    Transformations applied:
    1. Flatten anyOf to type arrays (n8n + ChatGPT)
    2. Add additionalProperties: false to all objects (ChatGPT)
    3. Make all fields required with nullable types (ChatGPT)

    Set THINGS_MCP_DEBUG_SCHEMA=1 to log full tool schemas for debugging.

    See:
    - n8n: https://github.com/n8n-io/n8n/issues/21500
    - ChatGPT: https://github.com/github/github-mcp-server/issues/376
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
                "ListToolsRequest handler - applying client compatibility patches"
            )
            result = await original_handler(request)
            # Result is ServerResult with root=ListToolsResult
            tools = result.root.tools

            # Transform each tool's inputSchema for client compatibility
            for tool in tools:
                if hasattr(tool, "inputSchema") and tool.inputSchema:
                    if debug_schema:
                        logger.info(
                            f"Tool '{tool.name}' BEFORE transforms: "
                            f"{json.dumps(tool.inputSchema, indent=2)}"
                        )

                    # Apply transformations in order
                    # 1. Flatten anyOf (n8n + ChatGPT)
                    transformed = _flatten_anyof_for_n8n(tool.inputSchema)
                    # 2. Add additionalProperties: false (ChatGPT)
                    transformed = _add_additional_properties_false(transformed)
                    # 3. Make all fields required (ChatGPT)
                    transformed = _make_all_fields_required(transformed)

                    # Modify the dict in place
                    if isinstance(tool.inputSchema, dict):
                        tool.inputSchema.clear()
                        tool.inputSchema.update(transformed)

                    if debug_schema:
                        logger.info(
                            f"Tool '{tool.name}' AFTER transforms: "
                            f"{json.dumps(tool.inputSchema, indent=2)}"
                        )

            logger.info(
                f"Processed {len(tools)} tools with client compatibility transforms"
            )
            return result

        request_handlers[mcp_types.ListToolsRequest] = patched_list_tools_handler
        logger.info(
            "Patched ListToolsRequest handler for n8n/ChatGPT schema compatibility"
        )
    except Exception as e:
        logger.warning(
            f"Could not patch ListToolsRequest handler for client compatibility: {e}"
        )

    # Also patch CallToolRequest to strip null values from arguments
    # n8n sends explicit nulls for empty optional fields
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
            f"Could not patch CallToolRequest handler for client compatibility: {e}"
        )


class ClientCompatibilityMiddleware(Middleware):
    """Handle client-specific quirks for n8n and ChatGPT compatibility.

    - Strips extra parameters that n8n sends (toolCallId, sessionId, etc.)
    - Strips null values that n8n sends for optional fields
    - Tracks tool call statistics for shutdown summary

    Note: ChatGPT doesn't send extra parameters, so these operations are
    harmless no-ops for ChatGPT clients.
    """

    async def on_call_tool(self, context, call_next):
        # Get tool name for stats tracking
        tool_name = None
        if hasattr(context, "message") and hasattr(context.message, "name"):
            tool_name = context.message.name

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

        # Execute the tool and track stats
        try:
            result = await call_next(context)
            if tool_name:
                server_stats.record_tool_call(tool_name, success=True)
            return result
        except Exception:
            if tool_name:
                server_stats.record_tool_call(tool_name, success=False)
            raise


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server instance."""
    server = FastMCP(
        "Things",
        instructions=INSTRUCTIONS_TEXT,
        website_url=WEBSITE_URL,
        icons=ICONS,
    )

    # Add client compatibility middleware for n8n and ChatGPT
    # - Strips extra parameters that n8n sends (toolCallId, sessionId, etc.)
    # - Strips null values for optional fields
    # See: https://github.com/n8n-io/n8n/issues/21500
    try:
        server.add_middleware(ClientCompatibilityMiddleware())
        logger.info("Client compatibility middleware registered (n8n/ChatGPT)")
    except Exception as e:
        logger.warning(f"Could not register client compatibility middleware: {e}")

    return server
