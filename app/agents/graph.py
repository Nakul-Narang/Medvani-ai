"""Pipeline wiring.

    translate_input -> safety_check -+-(emergency)--------> compose -> translate_output
                                     +-(no emergency)-> retrieve --^

Uses LangGraph when it is installed (production image) and falls back to a
plain-Python runner with identical behaviour when it is not (lightweight dev,
unit tests). Both paths run the same node functions.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from app.agents.nodes import Services, make_nodes
from app.agents.state import MedicalAgentState

logger = logging.getLogger(__name__)


class Pipeline(Protocol):
    engine: str

    def invoke(self, state: MedicalAgentState) -> MedicalAgentState: ...


def _route_after_safety(state: MedicalAgentState) -> str:
    return "compose" if state.get("emergency") else "retrieve"


class _SimplePipeline:
    engine = "simple"

    def __init__(self, nodes: dict[str, Any]) -> None:
        self._nodes = nodes

    def invoke(self, state: MedicalAgentState) -> MedicalAgentState:
        current: dict = dict(state)
        current.update(self._nodes["translate_input"](current))
        current.update(self._nodes["safety_check"](current))
        if _route_after_safety(current) == "retrieve":
            current.update(self._nodes["retrieve"](current))
        current.update(self._nodes["compose"](current))
        current.update(self._nodes["translate_output"](current))
        return current  # type: ignore[return-value]


class _LangGraphPipeline:
    engine = "langgraph"

    def __init__(self, compiled: Any) -> None:
        self._compiled = compiled

    def invoke(self, state: MedicalAgentState) -> MedicalAgentState:
        return self._compiled.invoke(state)


def build_pipeline(services: Services) -> Pipeline:
    nodes = make_nodes(services)
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        logger.info("langgraph not installed; using the simple pipeline runner")
        return _SimplePipeline(nodes)

    graph = StateGraph(MedicalAgentState)
    for name, fn in nodes.items():
        graph.add_node(name, fn)
    graph.set_entry_point("translate_input")
    graph.add_edge("translate_input", "safety_check")
    graph.add_conditional_edges(
        "safety_check", _route_after_safety, {"compose": "compose", "retrieve": "retrieve"}
    )
    graph.add_edge("retrieve", "compose")
    graph.add_edge("compose", "translate_output")
    graph.add_edge("translate_output", END)
    return _LangGraphPipeline(graph.compile())
