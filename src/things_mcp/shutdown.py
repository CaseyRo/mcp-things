"""Gracefully handle shutdown signals."""

import asyncio
import os
import signal
import logging


def setup_interrupt_handler(logger: logging.Logger | None = None) -> None:
    """Register SIGINT and SIGTERM handlers that stop the event loop and exit."""
    if logger is None:
        logger = logging.getLogger(__name__)

    def _shutdown(signum: int, frame) -> None:  # pragma: no cover - signal handler
        logger.info("Received interrupt signal, shutting down")
        try:
            loop = asyncio.get_event_loop()
            loop.stop()
        finally:
            os._exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
