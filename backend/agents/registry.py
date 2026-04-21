"""Registry for agent executors and contract lookup."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from agents.contracts import AgentContract, get_agent_contract
from workflow.state import CopilotState


AgentExecutor = Callable[[CopilotState], Awaitable[dict]]


class AgentRegistry:
    """Stores async executors and their contracts by agent name."""

    def __init__(self) -> None:
        self._executors: dict[str, AgentExecutor] = {}
        self._contracts: dict[str, AgentContract] = {}

    def register(self, agent_name: str, executor: AgentExecutor, contract: AgentContract | None = None) -> None:
        self._executors[agent_name] = executor
        self._contracts[agent_name] = contract or get_agent_contract(agent_name)

    def get_executor(self, agent_name: str) -> AgentExecutor:
        try:
            return self._executors[agent_name]
        except KeyError as exc:
            raise KeyError(f"Agent not registered: {agent_name}") from exc

    def get_contract(self, agent_name: str) -> AgentContract:
        try:
            return self._contracts[agent_name]
        except KeyError as exc:
            raise KeyError(f"Agent contract not registered: {agent_name}") from exc

    def has(self, agent_name: str) -> bool:
        return agent_name in self._executors

    def names(self) -> list[str]:
        return sorted(self._executors.keys())


_DEFAULT_REGISTRY: AgentRegistry | None = None


def build_default_registry() -> AgentRegistry:
    """Register the built-in workflow agents."""

    from agents.planner import planner_node_async
    from agents.implementations.jd_agent import jd_node_async
    from agents.implementations.profile_agent import profile_node_async
    from agents.implementations.gap_agent import gap_node_async
    from agents.implementations.content_agent import content_node_async
    from agents.implementations.render_agent import render_node_async
    from agents.implementations.interview_agent import interview_node_async

    registry = AgentRegistry()
    registry.register("planner", planner_node_async)
    registry.register("jd_agent", jd_node_async)
    registry.register("profile_agent", profile_node_async)
    registry.register("gap_agent", gap_node_async)
    registry.register("content_agent", content_node_async)
    registry.register("render_agent", render_node_async)
    registry.register("interview_agent", interview_node_async)
    return registry


def get_default_registry() -> AgentRegistry:
    """Return the shared default registry instance."""

    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = build_default_registry()
    return _DEFAULT_REGISTRY
