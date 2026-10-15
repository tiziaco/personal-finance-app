"""Shared observability components for agents."""

from app.agents.shared.observability.langfuse import create_graph_config, create_trace_config

__all__ = [
    "create_graph_config",
    "create_trace_config",
]
