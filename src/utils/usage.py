from contextlib import AbstractContextManager
from typing import Any, Dict

from langchain_community.callbacks import get_openai_callback
from config import MAX_RUN_COST


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
        self.tracker.nodes[self.node_name] = report
        return False


# General-purpose class that lets us track token usage and cost
# costs are tracked per node, so we can identify agents that are especially costly
class UsageTracker:
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.cost_limit = MAX_RUN_COST
        
    def isWithinLimit(self) -> bool:
        if self.cost_limit is None:
            return True
        total_cost = self.totalReport()["total_cost"]
        return total_cost <= self.cost_limit

    def generateOverBudgetMessage(self) -> str:
        total_cost = self.totalReport()["total_cost"]
        return (
            f"⚠️ Cost limit exceeded: ${total_cost:.6f} "
            f"(limit: ${self.cost_limit:.6f})"
        )

    def node(self, node_name: str, provider: str = "openai") -> AbstractContextManager:
        # TODO: add more models, if necessary?
        if provider == "openai":
            return _OpenAICallback(self, node_name)
        raise ValueError(f"unsupported provider: {provider}")

    # node starts at zero usage
    def zeroNode(self, node_name: str):
        self.nodes[node_name] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }

    # each agent is defined as a node, so this tells us the cost for that agent
    def nodeReport(self, node_name: str) -> Dict[str, Any]:
        return self.nodes.get(node_name, {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        })

    def totalReport(self) -> Dict[str, Any]:
        total_prompt_tokens = sum(v.get("prompt_tokens", 0) for v in self.nodes.values())
        total_completion_tokens = sum(v.get("completion_tokens", 0) for v in self.nodes.values())
        total_tokens = sum(v.get("total_tokens", 0) for v in self.nodes.values())
        total_cost = round(sum(float(v.get("total_cost", 0.0)) for v in self.nodes.values()), 6)
        return {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
        }
        
    def formatReport(self) -> str:
        lines = []
        lines.append("Per-agent usage:")
        for node, data in self.nodes.items():
            lines.append(
                f"  {node}: "
                f"{data['prompt_tokens']} in / "
                f"{data['completion_tokens']} out "
                f"(total {data['total_tokens']} tokens, "
                f"${data['total_cost']:.6f})"
            )
        totals = self.totalReport()
        lines.append("Totals:")
        lines.append(
            f"  {totals['prompt_tokens']} in / "
            f"{totals['completion_tokens']} out "
            f"(total {totals['total_tokens']} tokens, "
            f"${totals['total_cost']:.6f})"
        )
        return "\n".join(lines)
