from typing import Dict, Any
from contextlib import AbstractContextManager
from langchain_community.callbacks import get_openai_callback

# we use OpenAICallback to give us the up-to-date numbers like tokens per model and so on.
# as the name suggests, only works for OpenAI models
class _OpenAICallback(AbstractContextManager):
    def __init__(self, tracker: "UsageTracker", node_name: str):
        self.tracker = tracker
        self.node_name = node_name
        self._ctx = None
        self._handler = None

    def __enter__(self):
        self._ctx = get_openai_callback()
        self._handler = self._ctx.__enter__()
        return self._handler

    def __exit__(self, exc_type, exc, tb):
        self._ctx.__exit__(exc_type, exc, tb)
        report = {
            "prompt_tokens": int(getattr(self._handler, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(self._handler, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(self._handler, "total_tokens", 0) or 0),
            "total_cost": float(getattr(self._handler, "total_cost", 0.0) or 0.0),
        }
        self.tracker.node_usage[self.node_name] = report
        return False

# General-purpose class that lets us track token usage and cost
# costs are tracked per node, so we can identify agents that are especially costly
class UsageTracker:
    def __init__(self):
        self.node_usage: Dict[str, Dict[str, Any]] = {}

    def node(self, node_name: str, provider: str = "openai") -> AbstractContextManager:
        # TODO: add more models, if necessary?
        if provider == "openai":
            return _OpenAICallback(self, node_name)
        raise ValueError(f"unsupported provider: {provider}")

    # node starts at zero usage
    def zeroNode(self, node_name: str):
        self.node_usage[node_name] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }

    # each agent is defined as a node, so this tells us the cost for that agent
    def nodeReport(self, node_name: str) -> Dict[str, Any]:
        return self.node_usage.get(node_name, {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        })

    def totalReport(self) -> Dict[str, Any]:
        total_prompt_tokens = sum(v.get("prompt_tokens", 0) for v in self.node_usage.values())
        total_completion_tokens = sum(v.get("completion_tokens", 0) for v in self.node_usage.values())
        total_tokens = sum(v.get("total_tokens", 0) for v in self.node_usage.values())
        total_cost = round(sum(float(v.get("total_cost", 0.0)) for v in self.node_usage.values()), 6)
        return {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
        }