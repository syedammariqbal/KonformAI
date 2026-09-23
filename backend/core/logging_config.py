"""Logging configuration for KonformAI."""

import logging
import sys

from backend.core.config import settings


def setup_logging() -> None:
    """Configures structured console logging according to LOG_LEVEL."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    log_format = (
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Suppress verbose third-party loggers if needed
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)
