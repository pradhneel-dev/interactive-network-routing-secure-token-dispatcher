"""Single-user, in-memory application state (documented: restarting the backend resets everything)."""
from __future__ import annotations

from typing import Any

from .graph import Graph, demo_graph
from .security import KeyRegistry


class AppState:
    def __init__(self) -> None:
        self.graph: Graph = demo_graph()
        self.version = 1
        self.registry = KeyRegistry()
        self.batch: dict[str, Any] | None = None
        self.last_dispatch: dict[str, Any] | None = None

    def bump(self) -> None:
        self.version += 1

    def replace_graph(self, g: Graph) -> None:
        self.graph = g
        self.bump()
        self.batch = None
        self.last_dispatch = None


STATE = AppState()
