"""Tests for logging setup."""

import logging
from pathlib import Path

import pytest

from cii.utilities.logging import get_logger, setup_logging


class TestGetLogger:
    def test_root_logger(self) -> None:
        assert get_logger().name == "cii"

    def test_child_logger(self) -> None:
        assert get_logger("scanner").name == "cii.scanner"


class TestSetupLogging:
    def test_writes_to_file(self, tmp_path: Path) -> None:
        logger = setup_logging(level="INFO", console=False, log_dir=tmp_path)
        logger.info("hello from test")
        for handler in logger.handlers:
            handler.flush()
        content = (tmp_path / "cii.log").read_text()
        assert "hello from test" in content

    def test_repeated_setup_replaces_handlers(self, tmp_path: Path) -> None:
        logger = setup_logging(level="INFO", console=True, log_dir=tmp_path)
        first_handlers = list(logger.handlers)
        logger = setup_logging(level="DEBUG", console=True, log_dir=tmp_path)
        assert len(logger.handlers) == len(first_handlers) == 2
        assert logger.level == logging.DEBUG
        for handler in first_handlers:
            assert handler not in logger.handlers

    def test_console_only(self) -> None:
        logger = setup_logging(level="WARNING", console=True)
        assert len(logger.handlers) == 1
        assert logger.level == logging.WARNING

    def test_invalid_level_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="invalid log level"):
            setup_logging(level="LOUD", console=False, log_dir=tmp_path)

    def test_creates_log_dir(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        setup_logging(level="INFO", console=False, log_dir=log_dir)
        assert log_dir.is_dir()
