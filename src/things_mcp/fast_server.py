#!/usr/bin/env python3
"""Things MCP Server - Entry Point.

This module serves as the entry point for the Things MCP server.
It creates the server instance and registers all tools from the
modular tool files organized by GTD stage.

Architecture:
- server_core.py: Server factory, middleware, n8n patches
- tool_annotations.py: Shared tool annotations
- tools_gtd_core.py: Engage/Capture/Clarify stage tools
- tools_gtd_organize.py: Organize stage tools
- tools_gtd_reflect.py: Reflect stage tools
- tools_utility.py: Utility tools (search, list, show)
- tools_deprecated.py: Backward-compatible tool aliases
"""

import random
import signal
import sys

from .server_core import (
    create_mcp_server,
    get_binding_host,
    get_binding_port,
    _patch_tool_serialization_for_n8n,
    DEFAULT_HOST,
    HOST_ENV_VAR,
    server_stats,
    GTD_QUOTES,
)
from .cache import get_cache_stats
from .utils import app_state
from .url_scheme import launch_things
from .logging_config import setup_logging, get_logger

# Import tool registration functions
from .tools_gtd_core import register_gtd_core_tools
from .tools_gtd_organize import register_gtd_organize_tools
from .tools_gtd_reflect import register_gtd_reflect_tools
from .tools_utility import register_utility_tools
from .tools_deprecated import register_deprecated_tools

# Configure enhanced logging
setup_logging(console_level="INFO", file_level="DEBUG", structured_logs=True)
logger = get_logger(__name__)

# Create the FastMCP server
mcp = create_mcp_server()

# Register all tools organized by GTD stage
register_gtd_core_tools(mcp)  # Engage, Capture, Clarify
register_gtd_organize_tools(mcp)  # Organize
register_gtd_reflect_tools(mcp)  # Reflect
register_utility_tools(mcp)  # Utility (search, list, show, cache)
register_deprecated_tools(mcp)  # Backward compatibility


def _print_shutdown_summary():
    """Print a nice shutdown summary with stats."""
    stats = server_stats.get_summary()
    cache_stats = get_cache_stats()

    print("\n")
    print("=" * 50)
    print("  Things MCP Server - Session Summary")
    print("=" * 50)
    print(f"  Uptime:        {stats['uptime']}")
    print(f"  Tool calls:    {stats['total_calls']}")
    print(f"  Unique tools:  {stats['unique_tools']}")
    if stats["errors"] > 0:
        print(f"  Errors:        {stats['errors']}")

    if stats["top_tools"]:
        print("\n  Most used tools:")
        for tool_name, count in stats["top_tools"]:
            print(f"    - {tool_name}: {count}")

    print("\n  Cache stats:")
    print(f"    - Hits:      {cache_stats['hits']}")
    print(f"    - Misses:    {cache_stats['misses']}")
    print(f"    - Hit rate:  {cache_stats['hit_rate']}")

    print("\n" + "-" * 50)
    quote = random.choice(GTD_QUOTES)
    print(f"  {quote}")
    print("-" * 50)
    print("  Thanks for using Things MCP! Stay productive.")
    print("=" * 50)
    print("\n")


def run_things_mcp_server():
    """Run the Things MCP server."""

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        _print_shutdown_summary()
        logger.info(f"Received {sig_name}, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    host = get_binding_host()
    if host == DEFAULT_HOST:
        logger.info(
            "FastMCP will bind to %s (set %s=0.0.0.0 to allow remote connections)",
            DEFAULT_HOST,
            HOST_ENV_VAR,
        )
    else:
        logger.info(
            "FastMCP binding override detected: %s=%s",
            HOST_ENV_VAR,
            host,
        )

    # Ensure tool schema compatibility for n8n and other clients
    _patch_tool_serialization_for_n8n(mcp)

    # Check if Things app is available
    if not app_state.update_app_state():
        logger.warning(
            "Things app is not running at startup. MCP will attempt to launch it when needed."
        )
        try:
            # Try to launch Things
            if launch_things():
                logger.info("Successfully launched Things app")
            else:
                logger.error("Unable to launch Things app. Some operations may fail.")
        except Exception as e:
            logger.error(f"Error launching Things app: {str(e)}")
    else:
        logger.info("Things app is running and ready for operations")

    logger.info("Press Ctrl+C to stop the server")

    # Run the MCP server with HTTP transport
    mcp.run(
        transport="streamable-http",
        host=get_binding_host(),
        port=get_binding_port(),
    )


if __name__ == "__main__":
    run_things_mcp_server()
