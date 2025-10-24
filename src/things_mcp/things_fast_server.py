#!/usr/bin/env python3
"""
Main entry point for running the Things MCP server.
This version uses the modern FastMCP pattern for better maintainability.
"""
import logging
import sys
from rich.console import Console
from rich.logging import RichHandler
from .fast_server import run_things_mcp_server
from .shutdown import setup_interrupt_handler

# Configure rich logging
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger("things_fast_server")

# Exit immediately on Ctrl+C even if connections remain
setup_interrupt_handler(logger)

def main():
    """Main entry point for the Things FastMCP Server"""
    logger.info("Starting Things FastMCP Server")
    try:
        run_things_mcp_server()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception:
        logger.exception("Error running server")
        sys.exit(1)


if __name__ == "__main__":
    main()
