"""
logging_config.py — AUTOMATA centralized logging setup.

Owns:    Configuring the root Python logger for the entire backend process.
Never:   Does not write to files or external services — stdout only for now.
Ref:     TECH_STACK.md → "Logging" section.

Call `configure_logging()` exactly once at process startup, at the top of
`main.py` and `api/server.py` (in case server.py is used as the uvicorn
entry point directly). All subsequent `logging.getLogger(__name__)` calls
in any module inherit the configured formatter and level automatically.
"""

import logging
import os
import sys


def configure_logging() -> None:
    """
    Configure the root logger.

    Level is driven by the LOG_LEVEL environment variable (default: INFO).
    Format: ISO-8601 timestamp | level | module | message
    Handler: stdout stream — one line per log record.
    """
    level_name: str = os.getenv("LOG_LEVEL", "INFO").upper()
    level: int = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Clear any handlers that may have been added before configure_logging() was called
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Suppress overly verbose third-party loggers at DEBUG level
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured | level=%s", level_name
    )
