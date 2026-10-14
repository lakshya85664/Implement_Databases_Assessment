
from __future__ import annotations

import json
import logging
import time
from typing import Any


logger = logging.getLogger("database_tools")


def configure_logging(level: int = logging.INFO) -> None:
    """Configure logging while allowing standard logging capture."""
    logger.setLevel(level)
    logger.propagate = True


def emit_event(
    event_name: str,
    *,
    request_id: str,
    tool_name: str,
    status: str,
    duration_ms: float | None = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    """Create and log a structured event without raw tool arguments."""
    event: dict[str, Any] = {
        "event": event_name,
        "request_id": request_id,
        "tool_name": tool_name,
        "status": status,
    }

    if duration_ms is not None:
        event["duration_ms"] = round(max(0.0, duration_ms), 3)

    if error_type is not None:
        event["error_type"] = error_type

    logger.info(json.dumps(event, sort_keys=True))
    return event


class OperationTimer:
    """Measure elapsed time for an operation."""

    def __enter__(self) -> OperationTimer:
        self._started_at = time.perf_counter()
        self.duration_ms = 0.0
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.duration_ms = (
            time.perf_counter() - self._started_at
        ) * 1000.0
