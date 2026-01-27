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
    _patch_tool_serialization,
    DEFAULT_HOST,
    HOST_ENV_VAR,
    server_stats,
    GTD_QUOTES,
)
from .client_compat import (
    patch_accept_headers,
    get_streamable_http_middleware,
)
from .settings import get_transport
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
    """Print a beautiful shutdown summary with stats."""
    import re

    stats = server_stats.get_summary()
    cache_stats = get_cache_stats()

    # ANSI color codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    WHITE = "\033[97m"
    RED = "\033[31m"

    # Box-drawing characters
    TL = "╭"  # top-left
    TR = "╮"  # top-right
    BL = "╰"  # bottom-left
    BR = "╯"  # bottom-right
    H = "─"  # horizontal
    V = "│"  # vertical
    WIDTH = 58  # Total width including borders

    def visible_len(text: str) -> int:
        """Calculate visible length by stripping ANSI codes and accounting for emoji width."""
        # Strip ANSI codes
        clean = re.sub(r"\033\[[0-9;]*m", "", text)
        # Count emoji medals as 2 characters wide (they take 2 terminal cells)
        emoji_count = sum(1 for c in clean if c in "🥇🥈🥉")
        return (
            len(clean) + emoji_count
        )  # Add 1 extra for each emoji (already counted as 1)

    def hline(char=H):
        """Create horizontal line (WIDTH-2 chars to fit between corners)."""
        return char * (WIDTH - 2)

    def row(content: str) -> str:
        """Create a row with proper padding and borders."""
        vis_len = visible_len(content)
        # Content area is WIDTH - 2 (for left and right border)
        padding = WIDTH - 2 - vis_len
        return f"{CYAN}{V}{RESET}{content}{' ' * max(0, padding)}{CYAN}{V}{RESET}"

    print()
    print(f"{CYAN}{TL}{hline()}{TR}{RESET}")

    # Header
    print(row(f"  {BOLD}{WHITE}Things MCP Server{RESET}  {DIM}Session Complete{RESET}"))
    print(row(hline()))

    # Stats section
    print(row(""))
    print(row(f"  {BOLD}{YELLOW}SESSION STATS{RESET}"))
    print(row(""))
    print(row(f"    {DIM}Uptime{RESET}        {BOLD}{WHITE}{stats['uptime']}{RESET}"))
    print(
        row(f"    {DIM}Tool calls{RESET}    {BOLD}{GREEN}{stats['total_calls']}{RESET}")
    )
    print(row(f"    {DIM}Unique tools{RESET}  {WHITE}{stats['unique_tools']}{RESET}"))
    if stats["errors"] > 0:
        print(row(f"    {DIM}Errors{RESET}        {BOLD}{RED}{stats['errors']}{RESET}"))
    print(row(""))

    # Top tools
    if stats["top_tools"]:
        print(row(f"  {BOLD}{MAGENTA}TOP TOOLS{RESET}"))
        print(row(""))
        for i, (tool_name, count) in enumerate(stats["top_tools"]):
            bar_len = min(count * 2, 16)
            bar = "█" * bar_len
            # Emoji medals for top 3, dot for others
            # Note: emojis are 2 chars wide, so use 1 space after; dots use 2 spaces
            if i == 0:
                medal = "🥇"
                spacing = " "
            elif i == 1:
                medal = "🥈"
                spacing = " "
            elif i == 2:
                medal = "🥉"
                spacing = " "
            else:
                medal = " ·"
                spacing = " "
            print(
                row(
                    f"    {medal}{spacing}{WHITE}{tool_name:<18}{RESET} {GREEN}{bar:<16}{RESET} {DIM}{count}{RESET}"
                )
            )
        print(row(""))

    # Cache stats
    print(row(f"  {BOLD}{BLUE}CACHE PERFORMANCE{RESET}"))
    print(row(""))
    hit_rate_num = float(cache_stats["hit_rate"].replace("%", ""))
    hit_color = GREEN if hit_rate_num >= 50 else YELLOW if hit_rate_num >= 25 else RED
    cache_detail = f"({cache_stats['hits']} hits / {cache_stats['misses']} misses)"
    print(
        row(
            f"    {DIM}Hit rate{RESET}  {hit_color}{BOLD}{cache_stats['hit_rate']:>6}{RESET}  {DIM}{cache_detail}{RESET}"
        )
    )
    print(row(""))

    # Divider
    print(row(f"{DIM}{hline('·')}{RESET}"))

    # Quote
    quote = random.choice(GTD_QUOTES)
    # Word wrap the quote if needed
    max_quote_width = WIDTH - 10  # Leave room for borders and padding
    if len(quote) > max_quote_width:
        words = quote.split()
        lines = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 <= max_quote_width:
                current = current + " " + word if current else word
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        print(row(""))
        for line_text in lines:
            print(row(f'    {DIM}"{line_text}"{RESET}'))
        print(row(""))
    else:
        print(row(""))
        print(row(f'    {DIM}"{quote}"{RESET}'))
        print(row(""))

    # Footer
    print(row(hline()))
    print(
        row(
            f"  {GREEN}✓{RESET} {WHITE}Thanks for using Things MCP!{RESET} {DIM}Stay productive.{RESET}"
        )
    )
    print(f"{CYAN}{BL}{hline()}{BR}{RESET}")
    print()


def _create_combined_app(mcp_instance, transport_mode: str):
    """Create a combined ASGI app with dual transport support.

    Args:
        mcp_instance: The FastMCP server instance.
        transport_mode: One of "both", "sse", or "streamable-http".

    Returns:
        ASGI application with appropriate transport endpoints.
    """
    from starlette.applications import Starlette
    from starlette.routing import Mount

    routes = []

    if transport_mode in ("both", "sse"):
        # SSE transport for ChatGPT - no Accept header patches needed
        # ChatGPT expects SSE at /sse/ path
        sse_app = mcp_instance.http_app(transport="sse", path="/")
        routes.append(Mount("/sse", app=sse_app, name="sse"))
        logger.info("SSE transport enabled at /sse/ (for ChatGPT)")

    if transport_mode in ("both", "streamable-http"):
        # Apply Accept header patch for streamable-http transport
        patch_accept_headers()

        # Streamable-HTTP transport for Claude Desktop/n8n
        # Includes middleware for Accept header fixes as fallback
        http_middleware = get_streamable_http_middleware()
        http_app = mcp_instance.http_app(
            transport="streamable-http",
            path="/",
            middleware=http_middleware,
        )
        routes.append(Mount("/mcp", app=http_app, name="streamable-http"))
        logger.info(
            "Streamable-HTTP transport enabled at /mcp (for Claude Desktop/n8n)"
        )

    return Starlette(routes=routes)


def run_things_mcp_server():
    """Run the Things MCP server with dual transport support.

    Endpoints:
        /sse/ - SSE transport for ChatGPT
        /mcp - Streamable-HTTP transport for Claude Desktop, n8n
    """
    import uvicorn

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

    # Ensure tool schema compatibility for n8n and ChatGPT
    _patch_tool_serialization(mcp)

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

    # Get transport mode from settings
    transport_mode = get_transport()
    logger.info(f"Transport mode: {transport_mode}")

    # Create combined ASGI app with dual transport support
    combined_app = _create_combined_app(mcp, transport_mode)

    port = get_binding_port()
    logger.info("Server endpoints:")
    if transport_mode in ("both", "sse"):
        logger.info(f"  - SSE (ChatGPT):        http://{host}:{port}/sse/")
    if transport_mode in ("both", "streamable-http"):
        logger.info(f"  - Streamable-HTTP:      http://{host}:{port}/mcp")

    # Use wsproto to avoid deprecation warnings from websockets 14+
    # See: https://github.com/python-websockets/websockets/issues/975
    uvicorn.run(
        combined_app,
        host=host,
        port=port,
        ws="wsproto",
    )


if __name__ == "__main__":
    run_things_mcp_server()
