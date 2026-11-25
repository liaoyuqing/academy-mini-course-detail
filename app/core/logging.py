"""极简日志配置：结构化到行，便于 grep 降级告警。"""
from __future__ import annotations

import logging
import sys

from app.core.config import load_settings

_CONFIGURED = False


def _configure_once() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger("academy")
    root.handlers = [handler]
    root.setLevel(load_settings().log_level or "INFO")
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_once()
    return logging.getLogger(f"academy.{name}")

