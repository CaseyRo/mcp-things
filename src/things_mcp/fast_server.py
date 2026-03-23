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
    DEFAULT_HOST,
    HOST_ENV_VAR,
    server_stats,
    GTD_QUOTES,
)
from .client_compat import (
    patch_accept_headers,
    get_streamable_http_middleware,
)
from .settings import get_transport, is_debug_enabled, get_settings
from .cache import get_cache_stats
from .utils import app_state
from .url_scheme import launch_things
from .config import (
    ensure_auth_token,
    ensure_api_key,
    enforce_file_permissions,
)
from .logging_config import setup_logging, get_logger

# Import tool registration functions
from .tools_gtd_core import register_gtd_core_tools
from .tools_gtd_organize import register_gtd_organize_tools
from .tools_gtd_reflect import register_gtd_reflect_tools
from .tools_utility import register_utility_tools
from .tools_batch import register_batch_tools

# Configure enhanced logging
# Console shows DEBUG if THINGS_MCP_DEBUG=true, otherwise INFO
_console_level = "DEBUG" if is_debug_enabled() else "INFO"
setup_logging(console_level=_console_level, file_level="DEBUG", structured_logs=True)
logger = get_logger(__name__)

# Ensure API key exists before creating server (so auth provider gets it)
_api_key, _api_key_is_new = ensure_api_key()

# Enforce secure file permissions on startup
enforce_file_permissions()

# Create the FastMCP server (with auth if API key is configured)
mcp = create_mcp_server()

# Register all tools organized by GTD stage
register_gtd_core_tools(mcp)  # Engage, Capture, Clarify
register_gtd_organize_tools(mcp)  # Organize
register_gtd_reflect_tools(mcp)  # Reflect
register_utility_tools(mcp)  # Utility (search, list, show, cache)
register_batch_tools(mcp)  # Batch (bulk-capture, bulk-complete, etc.)


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


class _TrailingSlashMiddleware:
    """ASGI middleware that silently adds trailing slash to /mcp requests.

    This avoids 307 redirects by normalizing the path internally before
    it reaches Starlette's router, eliminating the extra round-trip.
    Preserves access to the wrapped app's attributes (routes, router, etc.).
    """

    def __init__(self, app):
        self.app = app

    def __getattr__(self, name):
        # Delegate attribute access to the wrapped app
        return getattr(self.app, name)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/mcp":
            # Silently rewrite /mcp to /mcp/ without a redirect
            scope = dict(scope)
            scope["path"] = "/mcp/"
        await self.app(scope, receive, send)


class _OAuthDiscoveryGateMiddleware:
    """ASGI middleware that blocks OAuth discovery for non-public-URL requests.

    OAuth metadata (/.well-known/*) should only be served when accessed via
    the public URL (through Caddy reverse proxy). Direct/Tailscale connections
    get 404, causing MCP clients like Claude Code to fall back to bearer token
    auth instead of attempting OAuth with Keycloak.

    This operates at the ASGI level to catch .well-known requests regardless
    of whether they're served by root-level routes or inside mounted sub-apps.
    """

    def __init__(self, app, public_host: str):
        self.app = app
        self.public_host = public_host
        # Domain without port for prefix matching
        self.public_domain = public_host.split(":")[0]

    def __getattr__(self, name):
        return getattr(self.app, name)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and "/.well-known/" in scope.get("path", ""):
            # Extract Host header from raw ASGI headers
            host = ""
            for key, value in scope.get("headers", []):
                if key == b"host":
                    host = value.decode("latin-1")
                    break

            if host != self.public_host and not host.startswith(self.public_domain):
                # Not from public URL — return 404 to force bearer token fallback
                await send(
                    {
                        "type": "http.response.start",
                        "status": 404,
                        "headers": [(b"content-type", b"text/plain")],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b"Not Found",
                    }
                )
                return

        await self.app(scope, receive, send)


def _create_combined_app(mcp_instance, transport_mode: str):
    """Create an ASGI app with streamable-http transport support.

    Args:
        mcp_instance: The FastMCP server instance.
        transport_mode: Must be "streamable-http" (SSE transport removed).

    Returns:
        ASGI application with streamable-http transport endpoint.
    """
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from starlette.responses import HTMLResponse, JSONResponse

    from .triage_tracker import triage_tracker
    from pathlib import Path
    import json

    # Dashboard template path (co-located in package)
    _dashboard_path = Path(__file__).parent / "dashboard.html"

    _security_headers = {
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'",
        "Referrer-Policy": "no-referrer",
    }

    def _parse_days(request) -> int:
        """Parse and clamp the 'days' query parameter."""
        try:
            days = int(request.query_params.get("days", 30))
        except (ValueError, TypeError):
            days = 30
        return max(0, min(days, 365))

    async def dashboard_page(request):
        """Serve the GTD Health Dashboard with live triage data."""
        days = _parse_days(request)
        data = _build_dashboard_data(triage_tracker, days)

        template = _dashboard_path.read_text()
        # Inject data as a global JS variable before the closing </head>
        data_script = (
            "<script>window.__TRIAGE_DATA__ = "
            + json.dumps(data)
            + ";</script>\n</head>"
        )
        html = template.replace("</head>", data_script, 1)
        return HTMLResponse(html, headers=_security_headers)

    async def dashboard_data(request):
        """Return triage data as JSON (for period switching via JS)."""
        days = _parse_days(request)
        data = _build_dashboard_data(triage_tracker, days)
        return JSONResponse(data, headers=_security_headers)

    routes = [
        Route("/dashboard", dashboard_page),
        Route("/dashboard/data", dashboard_data),
    ]

    # Apply Accept header patch for streamable-http transport
    patch_accept_headers()

    # Streamable-HTTP transport for Claude Desktop/n8n/ChatGPT
    # Includes middleware for Accept header fixes as fallback
    http_middleware = get_streamable_http_middleware()
    http_app = mcp_instance.http_app(
        transport="streamable-http",
        path="/",
        middleware=http_middleware,
    )
    # Mount well-known routes at root level (RFC 9728 requires this).
    # Auth routes (e.g. /.well-known/oauth-protected-resource) must live
    # at the root, not under /mcp, so MCP clients can discover them.
    if mcp_instance.auth:
        auth_routes = mcp_instance.auth.get_routes("")
        routes.extend(auth_routes)
        route_paths = [r.path for r in auth_routes if hasattr(r, "path")]
        logger.info("Auth routes mounted at root: %s", route_paths)

    routes.append(Mount("/mcp", app=http_app, name="streamable-http"))
    logger.info(
        "Streamable-HTTP transport enabled at /mcp (for Claude Desktop/n8n/ChatGPT)"
    )

    # Use FastMCP's lifespan directly as recommended by the error message.
    # FastMCP's http_app() returns a StarletteWithLifespan instance that includes
    # the proper lifespan for initializing the streamable-http transport's task group.
    # Without using this lifespan directly, requests fail with:
    # "RuntimeError: Task group is not initialized. Make sure to use run()."
    app = Starlette(routes=routes, lifespan=http_app.lifespan)

    # Wrap with middleware to silently normalize /mcp to /mcp/ (avoids 307 redirects)
    app = _TrailingSlashMiddleware(app)

    # Gate OAuth discovery endpoints to public URL only.
    # Direct/Tailscale connections get 404 for /.well-known/* paths,
    # forcing Claude Code to fall back to bearer token auth instead of
    # attempting OAuth with Keycloak. Caddy connections (public URL host)
    # still get OAuth metadata for Claude.ai connector.
    public_url = get_settings().things_mcp_public_url
    if public_url:
        public_host = public_url.rstrip("/").split("://")[-1]
        app = _OAuthDiscoveryGateMiddleware(app, public_host)
        logger.info(
            "OAuth discovery gated to public host: %s (direct connections use bearer token)",
            public_host,
        )

    return app


def _build_dashboard_data(tracker, days: int) -> dict:
    """Build the data payload for the dashboard."""
    summary = tracker.get_summary(days=days)
    trends = tracker.get_trends(weeks=max(days // 7, 4) if days > 0 else 12)
    return {
        "days": days,
        "summary": summary,
        "trends": trends,
    }


def run_things_mcp_server():
    """Run the Things MCP server with streamable-http transport support.

    Endpoints:
        /mcp - Streamable-HTTP transport for Claude Desktop, n8n, ChatGPT
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

    # Ensure auth token is configured before starting
    token = ensure_auth_token()
    if not token:
        logger.error(
            "No auth token configured. Server will start but write operations will fail."
        )

    host = get_binding_host()
    if host == DEFAULT_HOST:
        logger.info(
            "FastMCP will bind to %s (set %s=0.0.0.0 to allow remote connections)",
            DEFAULT_HOST,
            HOST_ENV_VAR,
        )
    else:
        if _api_key:
            logger.info(
                "Server binding to %s with bearer token authentication enabled.",
                host,
            )
        else:
            logger.warning(
                "SECURITY WARNING: Server is binding to %s with no authentication. "
                "All MCP tools are publicly accessible. Only do this on trusted networks.",
                host,
            )

    # Display API key info for client configuration
    if _api_key:
        masked = _api_key[:9] + "..." + _api_key[-4:]
        if _api_key_is_new:
            # First run: show full key so user can configure clients
            logger.warning(
                "NEW API key generated: %s — save this for your MCP client config",
                _api_key,
            )
            print(f"\n  NEW API Key: {_api_key}")
            print("  Configure MCP clients with: Authorization: Bearer <key>")
            print("  Stored in: .env (THINGS_MCP_API_KEY)\n")
        else:
            logger.info(
                "API key active: %s — clients must send: Authorization: Bearer <key>",
                masked,
            )

    # Display Keycloak JWT validation info
    from .settings import get_keycloak_issuer, get_keycloak_audience

    kc_issuer = get_keycloak_issuer()
    kc_audience = get_keycloak_audience()
    if kc_issuer:
        logger.info(
            "Keycloak JWT validation: issuer=%s audience=%s",
            kc_issuer,
            kc_audience,
        )

    # Schema compatibility is now handled by ClientCompatibilityMiddleware.on_list_tools
    # which detects the client type and applies transforms accordingly:
    # - All clients: anyOf flattening (type arrays)
    # - ChatGPT only: additionalProperties:false + all-fields-required

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

    # Create ASGI app with streamable-http transport support
    combined_app = _create_combined_app(mcp, transport_mode)

    port = get_binding_port()
    logger.info("Server endpoints:")
    logger.info(f"  - Streamable-HTTP:      http://{host}:{port}/mcp")
    logger.info(f"  - Dashboard:            http://{host}:{port}/dashboard")

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
