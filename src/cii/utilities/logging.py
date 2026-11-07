"""Logging setup for CII.

CII logs to stderr (optional) and to ``<project-root>/.cii/logs/cii.log``
(optional, rotating). All modules obtain loggers through :func:`get_logger`
so output is consistently namespaced under ``cii``.
"""

import logging
import logging.handlers
from pathlib import Path

LOGGER_ROOT = "cii"
LOG_FILE_NAME = "cii.log"
_MAX_LOG_BYTES = 1_000_000
_BACKUP_COUNT = 3

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the ``cii`` namespace.

    ``name`` is appended to the namespace, e.g. ``get_logger("scanner")``
    returns the ``cii.scanner`` logger.
    """
    if not name:
        return logging.getLogger(LOGGER_ROOT)
    return logging.getLogger(f"{LOGGER_ROOT}.{name}")


def setup_logging(
    *,
    level: str = "INFO",
    console: bool = True,
    log_dir: Path | None = None,
) -> logging.Logger:
    """Configure the ``cii`` root logger.

    Repeated calls replace existing handlers instead of stacking duplicates.

    Args:
        level: Minimum log level name (e.g. ``"INFO"``).
        console: When True, log to stderr.
        log_dir: When provided, log to ``<log_dir>/cii.log`` with rotation.

    Raises:
        ValueError: ``level`` is not a valid logging level name.
    """
    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        raise ValueError(f"invalid log level: {level!r}")

    logger = logging.getLogger(LOGGER_ROOT)
    logger.setLevel(numeric_level)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / LOG_FILE_NAME,
            maxBytes=_MAX_LOG_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
