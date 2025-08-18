# types.py
from __future__ import annotations

from enum import Enum
from typing import Dict, TypedDict, Optional, Callable, Any, Awaitable, List

sse_headers = {
        "Content-Type": "text/event-stream; charset=utf-8",
        "X-Accel-Buffering": "no",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

EventCallback = Callable[[str, Dict[str, Any]], Awaitable[None]]

class Status(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    COMPLETED = "completed"


class AgentResponse:
    def __init__(self, response: str, status: Status, err_message: Optional[str] = None):
        self.response = response
        self.status = status
        self.err_message = err_message


class WorkflowContext:
    def __init__(
        self,
        start_time_ns: Optional[int] = None,
        end_time_ns: Optional[int] = None,
        duration_ns: Optional[int] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        cost: float = 0.0,
    ):
        self.start_time_ns = start_time_ns
        self.end_time_ns = end_time_ns
        self.duration_ns = duration_ns
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens
        self.cost = cost


class WorkflowState:
    def __init__(
        self,
        current_workflow: str,
        current_stage: Optional[str],
        context: Dict[str, Dict],
        memory: Optional[Dict[str, Dict]],
        status: Status,
        err_message: Optional[str] = None,
        workflows_context: Optional[Dict[str, WorkflowContext]] = None,
    ):
        self.current_workflow = current_workflow
        self.current_stage = current_stage or ""
        self.context = context
        self.memory = memory or {}
        self.status = status
        self.err_message = err_message or ""
        self.workflows_context = workflows_context or {}


class Event(TypedDict):
    workflow_names: List[str]
    status: Status
    err_message: str
    
