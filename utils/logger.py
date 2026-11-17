"""Structured rotating logger utility for application events, API calls, and errors."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(DATA_DIR, "app.log")


def get_logger(name: str = "career_assistant") -> logging.Logger:
    """Return a configured logger writing to both rotating file and stream handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        file_handler = RotatingFileHandler(
            LOG_FILE_PATH, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Fallback cleanly if log file cannot be opened in restricted environments
        pass

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


def log_api_call(
    provider: str,
    task: str,
    status: str,
    tokens: int = 0,
    cost_usd: float = 0.0,
    details: Optional[str] = None,
) -> None:
    """Log an LLM or external API invocation without exposing secrets."""
    logger = get_logger("api")
    msg = (
        f"provider={provider} task={task} status={status} "
        f"tokens={tokens} est_cost=${cost_usd:.6f}"
    )
    if details:
        msg += f" details={details[:200]}"
    if status.lower() in {"error", "failed"}:
        logger.error(msg)
    else:
        logger.info(msg)


def log_user_event(user_id: Optional[int], action: str, details: str = "") -> None:
    """Log a user-facing milestone or navigation event."""
    logger = get_logger("audit")
    logger.info("user_id=%s action=%s details=%s", user_id, action, details[:250])
