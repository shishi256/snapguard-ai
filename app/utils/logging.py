"""
Structured rotating file logger for SnapGuard AI.
"""

import logging
import logging.handlers
from pathlib import Path
from app.config import LOGS_DIR, APP_NAME


def setup_logger(name: str = APP_NAME, level: int = logging.DEBUG) -> logging.Logger:
    """
    Create and return a logger with both console and rotating file handlers.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(level)
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Rotating file handler (10 MB × 5 backups)
    log_file = LOGS_DIR / "snapguard.log"
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


# Module-level convenience logger
log = setup_logger()
