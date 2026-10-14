
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AccessMode(str, Enum):
    READ = "read"
    WRITE = "write"


class ToolStatus(str, Enum):
    OK = "ok"
    INVALID = "invalid"
    DENIED = "denied"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PROVIDER_ERROR = "provider_error"
    FAILED = "failed"
    PENDING_APPROVAL = "pending_approval"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    access_mode: AccessMode
    roles: frozenset[str]
    input_model: type
    output_model: type
    description: str


@dataclass
class ToolCall:
    request_id: str
    tool_name: str
    version: str
    arguments: dict[str, Any]
    principal: str
    role: str


@dataclass
class ToolResult:
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    next_action: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
