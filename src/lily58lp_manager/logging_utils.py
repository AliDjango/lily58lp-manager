"""Logging helpers for failures that may repeat on every telemetry cycle."""

from __future__ import annotations

import logging
from threading import Lock
from time import monotonic


class RateLimitedWarnings:
    def __init__(self, logger: logging.Logger, interval_seconds: float = 30.0) -> None:
        self._logger = logger
        self._interval_seconds = interval_seconds
        self._last_emitted: dict[str, float] = {}
        self._lock = Lock()

    def warning(self, key: str, message: str, *args: object) -> None:
        now = monotonic()
        with self._lock:
            previous = self._last_emitted.get(key)
            if previous is not None and now - previous < self._interval_seconds:
                return
            self._last_emitted[key] = now
        self._logger.warning(message, *args)
