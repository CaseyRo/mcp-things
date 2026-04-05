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
from .settings import (
    get_settings,
    get_keycloak_issuer,
)

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
    "**Support**: https://github.com/CaseyRo/mcp-things/issues\n"
)

WEBSITE_URL = "https://github.com/CaseyRo/mcp-things"

# Default values for documentation purposes
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8009
HOST_ENV_VAR = "THINGS_MCP_HOST"

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
        src="https://culturedcode.com/things/2024-01-20/images/hero-logo-things-io90.png",
        mime_type="image/png",
    ),
]


def _error_result(message: str):
    """Raise a ToolError for standardized MCP error handling.

    FastMCP v3 uses ToolError for proper error propagation to clients.
    """
    raise ToolError(message)


def get_binding_host() -> str:
    """Return the host for the FastMCP server from settings."""
    return get_settings().things_mcp_host


def get_binding_port() -> int:
    """Return the port for the FastMCP server from settings."""
    return get_settings().things_mcp_port


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


class ClientCompatibilityMiddleware(Middleware):
    """Handle client-specific quirks for n8n and ChatGPT compatibility.

    on_list_tools:
    - Detects client via User-Agent header
    - Always flattens anyOf constructs (all clients need this)
    - Only applies ChatGPT strict-mode transforms (additionalProperties:false,
      all-fields-required) when the client is ChatGPT

    on_call_tool:
    - Strips extra parameters that n8n sends (toolCallId, sessionId, etc.)
    - Strips null values that n8n sends for optional fields
    - Tracks tool call statistics for shutdown summary
    """

    def _detect_client(self) -> str:
        """Detect the MCP client type from HTTP headers.

        Returns one of: "chatgpt", "n8n", "claude", or "unknown".
        """
        try:
            from fastmcp.server.dependencies import get_http_headers

            headers = get_http_headers(include_all=True)
            user_agent = headers.get("user-agent", "").lower()

            if "chatgpt" in user_agent or "openai" in user_agent:
                return "chatgpt"
            if "n8n" in user_agent:
                return "n8n"
            if "claude" in user_agent or "anthropic" in user_agent:
                return "claude"
        except Exception:
            pass
        return "unknown"

    async def on_list_tools(self, context, call_next):
        """Apply client-aware schema transforms to tool listings.

        All clients get anyOf flattening (type arrays are valid JSON Schema).
        Only ChatGPT gets the strict-mode transforms that make every field
        required — other clients keep normal optional parameters.
        """
        tools = await call_next(context)

        client = self._detect_client()
        is_chatgpt = client == "chatgpt"

        if is_chatgpt:
            logger.info(
                "ChatGPT client detected — applying strict-mode schema transforms"
            )
        else:
            logger.debug(
                f"Client '{client}' — applying standard schema transforms (anyOf only)"
            )

        for tool in tools:
            if hasattr(tool, "parameters") and tool.parameters:
                # 1. Always flatten anyOf → type arrays (all clients)
                transformed = _flatten_anyof_for_n8n(tool.parameters)

                # 2-3. Only for ChatGPT: strict-mode transforms
                if is_chatgpt:
                    transformed = _add_additional_properties_false(transformed)
                    transformed = _make_all_fields_required(transformed)

                tool.parameters.clear()
                tool.parameters.update(transformed)

        logger.info(f"Processed {len(tools)} tool schemas for client '{client}'")
        return tools

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
    from .auth import create_auth

    settings = get_settings()

    # Public URL is used as the resource identifier in Protected Resource
    # Metadata (RFC 9728). Must be HTTPS for remote clients.
    if settings.things_mcp_public_url:
        base_url = settings.things_mcp_public_url.rstrip("/")
    else:
        base_url = f"http://{settings.things_mcp_host}:{settings.things_mcp_port}"

    keycloak_client_secret = settings.keycloak_client_secret

    if not keycloak_client_secret:
        logger.warning(
            "KEYCLOAK_CLIENT_SECRET not set — auth disabled. "
            "Set it to enable OAuth via Keycloak."
        )
        auth = None
    else:
        auth = create_auth(
            base_url=base_url,
            keycloak_issuer=get_keycloak_issuer(),
            keycloak_client_id=settings.keycloak_client_id,
            keycloak_client_secret=keycloak_client_secret,
        )

    server = FastMCP(
        "Things",
        instructions=INSTRUCTIONS_TEXT,
        website_url=WEBSITE_URL,
        icons=ICONS,
        auth=auth,
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
