# types.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, Optional
import time

class Status(str, Enum):
    STARTED = "started"
    PROGRESS = "progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

@dataclass
class TokenCost:
    inputTokens: int = 0
    outputTokens: int = 0
    totalTokens: int = 0
    estimatedCost: float = 0.0

@dataclass
class StageEvent:
    stage: str
    status: Status
    substage: Optional[str] = None
    attempt: Optional[int] = None
    startedAt: Optional[int] = None  # epoch ms
    endedAt: Optional[int] = None
    durationMs: Optional[int] = None
    tokenCost: Optional[TokenCost] = None
    result: Optional[str] = None
    netlist: Optional[str] = None
    error: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RunState:
    requirements: str
    bag: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RunContext:
    usage: Any  # your UsageTracker
    cost_limits_ok: callable  # function that returns bool

class Timer:
    def __init__(self):
        self._t0_perf = time.perf_counter()
        self._t0_ms = int(time.time() * 1000)
        self._end_ms: Optional[int] = None

    @property
    def start_ms(self) -> int:
        return self._t0_ms

    def finish(self):
        if self._end_ms is None:
            self._end_ms = int(time.time() * 1000)
        dur = int((time.perf_counter() - self._t0_perf) * 1000)
        return self._t0_ms, self._end_ms, dur
