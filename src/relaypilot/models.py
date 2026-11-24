from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RunState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    HANDOFF = "handoff"
    COMPLETED = "completed"
    LAUNCH_REQUESTED = "launch_requested"
    BLOCKED = "blocked"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True)
class Action:
    kind: str
    arguments: dict[str, Any] = field(default_factory=dict)
    external_effect: bool = False


@dataclass
class Event:
    message: str
    evidence: str = ""


@dataclass
class RunResult:
    state: RunState
    events: list[Event] = field(default_factory=list)
    saved_path: Path | None = None
    opened_path: Path | None = None
    reason: str | None = None

