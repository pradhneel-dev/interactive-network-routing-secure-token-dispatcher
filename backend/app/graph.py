"""Graph engine (Unit 6): hand-written graph structure, traversal traces, routing and analysis.

All algorithms are implemented manually (no NetworkX) so each step can be explained in a viva.
Neighbour iteration is alphabetical so traces are deterministic and reproducible.
"""
from __future__ import annotations

import heapq
import math
from collections import deque
from typing import Any, Iterable

MAX_HAMILTONIAN_NODES = 10
MAX_PATH_COUNT_NODES = 10


class GraphError(ValueError):
    """Domain error for graph operations. Carries a machine code and HTTP status."""

    def __init__(self, message: str, code: str = "invalid_graph", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _clean_name(name: Any) -> str:
    if not isinstance(name, str):
        raise GraphError("Node id must be a string.", "invalid_node")
    name = name.strip()
    if not name:
        raise GraphError("Node id must not be empty.", "invalid_node")
    if len(name) > 64:
        raise GraphError("Node id must be 64 characters or fewer.", "invalid_node")
    if "/" in name or "\\" in name or any(ord(char) < 32 for char in name):
        raise GraphError("Node id cannot contain path separators or control characters.", "invalid_node")
    return name


def _clean_weight(weight: Any) -> float:
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise GraphError("Edge weight must be a number.", "invalid_weight")
    w = float(weight)
    if math.isnan(w) or math.isinf(w):
        raise GraphError("Edge weight must be a finite number.", "invalid_weight")
    if w < 0:
        raise GraphError(
            "Negative edge weights are rejected (Dijkstra requires non-negative weights).",
            "negative_weight",
        )
    return w


class Graph:
    """Undirected weighted graph stored as an adjacency list: node -> {neighbour: weight}."""

    def __init__(self) -> None:
        self.adj: dict[str, dict[str, float]] = {}
        self.positions: dict[str, dict[str, float]] = {}
        # Routing cost is stored in adj; physical/simulation properties are separate.
        self.edge_properties: dict[tuple[str, str], dict[str, Any]] = {}
        self.node_properties: dict[str, dict[str, Any]] = {}

    # ---------------------------------------------------------------- CRUD
    def add_node(self, name: Any, x: float | None = None, y: float | None = None) -> str:
        name = _clean_name(name)
        if name in self.adj:
            raise GraphError(f"Node '{name}' already exists.", "duplicate_node", 409)
        self.adj[name] = {}
        self.node_properties[name] = {"status": "up"}
        if x is not None and y is not None:
            self.positions[name] = {"x": float(x), "y": float(y)}
        return name

    def remove_node(self, name: str) -> None:
        self.require(name)
        for nb in list(self.adj[name]):
            del self.adj[nb][name]
        for key in [key for key in self.edge_properties if name in key]:
            self.edge_properties.pop(key, None)
        del self.adj[name]
        self.positions.pop(name, None)
        self.node_properties.pop(name, None)

    def require(self, name: str) -> None:
        if name not in self.adj:
            raise GraphError(f"Unknown node '{name}'.", "unknown_node", 404)

    def has_edge(self, u: str, v: str) -> bool:
        return u in self.adj and v in self.adj[u]

    @staticmethod
    def _edge_key(u: str, v: str) -> tuple[str, str]:
        return (u, v) if u <= v else (v, u)

    def add_edge(self, u: Any, v: Any, weight: Any, *, propagation_delay_ms: Any = 1.0,
                 capacity_mbps: Any = 10.0, loss_probability: Any = 0.0,
                 queue_capacity_packets: Any = 20, status: str = "up") -> None:
        u, v = _clean_name(u), _clean_name(v)
        if u == v:
            raise GraphError("Self-loops are not allowed.", "self_loop")
        w = _clean_weight(weight)
        self.require(u)
        self.require(v)
        if self.has_edge(u, v):
            raise GraphError(f"Edge {u} - {v} already exists; update it instead.", "duplicate_edge", 409)
        self.adj[u][v] = w
        self.adj[v][u] = w
        self.set_edge_properties(u, v, propagation_delay_ms=propagation_delay_ms,
                                 capacity_mbps=capacity_mbps, loss_probability=loss_probability,
                                 queue_capacity_packets=queue_capacity_packets, status=status)

    def set_edge_properties(self, u: str, v: str, *, propagation_delay_ms: Any = 1.0,
                            capacity_mbps: Any = 10.0, loss_probability: Any = 0.0,
                            queue_capacity_packets: Any = 20, status: str = "up") -> None:
        if not self.has_edge(u, v):
            raise GraphError(f"Edge {u} - {v} does not exist.", "unknown_edge", 404)
        try:
            delay = float(propagation_delay_ms)
            capacity = float(capacity_mbps)
            loss = float(loss_probability)
            queue_capacity = int(queue_capacity_packets)
        except (TypeError, ValueError):
            raise GraphError("Invalid link simulation properties.", "invalid_link_properties")
        if not math.isfinite(delay) or delay < 0:
            raise GraphError("Propagation delay must be finite and non-negative.", "invalid_link_properties")
        if not math.isfinite(capacity) or capacity <= 0:
            raise GraphError("Link capacity must be finite and positive.", "invalid_link_properties")
        if not math.isfinite(loss) or not 0 <= loss <= 1:
            raise GraphError("Loss probability must be between 0 and 1.", "invalid_link_properties")
        if queue_capacity < 1:
            raise GraphError("Queue capacity must be at least one packet.", "invalid_link_properties")
        if status not in {"up", "down"}:
            raise GraphError("Link status must be 'up' or 'down'.", "invalid_link_properties")
        self.edge_properties[self._edge_key(u, v)] = {
            "propagation_delay_ms": delay, "capacity_mbps": capacity,
            "loss_probability": loss, "queue_capacity_packets": queue_capacity, "status": status,
        }

    def get_edge_properties(self, u: str, v: str) -> dict[str, Any]:
        if not self.has_edge(u, v):
            raise GraphError(f"Edge {u} - {v} does not exist.", "unknown_edge", 404)
        return dict(self.edge_properties.get(self._edge_key(u, v), {
            "propagation_delay_ms": 1.0, "capacity_mbps": 10.0,
            "loss_probability": 0.0, "queue_capacity_packets": 20, "status": "up",
        }))

    def update_edge(self, u: str, v: str, weight: Any, **properties: Any) -> None:
        w = _clean_weight(weight)
        if not self.has_edge(u, v):
            raise GraphError(f"Edge {u} - {v} does not exist.", "unknown_edge", 404)
        self.adj[u][v] = w
        self.adj[v][u] = w
        if properties:
            existing = self.get_edge_properties(u, v)
            existing.update(properties)
            self.set_edge_properties(u, v, **existing)

    def remove_edge(self, u: str, v: str) -> None:
        if not self.has_edge(u, v):
            raise GraphError(f"Edge {u} - {v} does not exist.", "unknown_edge", 404)
        del self.adj[u][v]
        del self.adj[v][u]
        self.edge_properties.pop(self._edge_key(u, v), None)

    def clear(self) -> None:
        self.adj.clear()
        self.positions.clear()
        self.edge_properties.clear()
        self.node_properties.clear()

    # ------------------------------------------------------------ queries
    @property
    def nodes(self) -> list[str]:
        return list(self.adj)

    def edges(self) -> list[tuple[str, str, float]]:
        index = {n: i for i, n in enumerate(self.adj)}
        out = []
        for u in self.adj:
            for v, w in self.adj[u].items():
                if index[u] < index[v]:
                    out.append((u, v, w))
        return out

    def neighbors(self, u: str) -> list[str]:
        return sorted(self.adj[u])

    def degree(self, u: str) -> int:
        return len(self.adj[u])

    def adjacency_list(self) -> dict[str, list[dict[str, Any]]]:
        return {u: [{"node": v, "weight": self.adj[u][v]} for v in self.neighbors(u)] for u in self.adj}

    def adjacency_matrix(self) -> dict[str, Any]:
        labels = self.nodes
        matrix = [[self.adj[a].get(b, 0) for b in labels] for a in labels]
        return {"labels": labels, "matrix": matrix, "note": "0 means no edge (weights are non-negative; a 0-weight edge is also shown as 0)."}

    def path_cost(self, path: list[str]) -> float:
        return sum(self.adj[a][b] for a, b in zip(path, path[1:]))

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [{"id": n, **self.positions.get(n, {}), **self.node_properties.get(n, {"status": "up"})} for n in self.adj],
            "edges": [{"u": u, "v": v, "weight": w, **self.get_edge_properties(u, v)} for u, v, w in self.edges()],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Graph":
        """Validate and build a graph from the SRS JSON shape; raises GraphError without partial state."""
        if not isinstance(data, dict):
            raise GraphError("Graph JSON must be an object with 'nodes' and 'edges'.", "invalid_json")
        nodes, edges = data.get("nodes"), data.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise GraphError("Graph JSON needs 'nodes' (list) and 'edges' (list).", "invalid_json")
        g = cls()
        positions = data.get("positions") if isinstance(data.get("positions"), dict) else {}
        for item in nodes:
            if isinstance(item, dict):
                g.add_node(item.get("id"), item.get("x"), item.get("y"))
                if item.get("status") in {"up", "down"}:
                    g.node_properties[str(item.get("id"))]["status"] = item["status"]
            else:
                g.add_node(item)
        for name, pos in positions.items():
            if name in g.adj and isinstance(pos, dict) and "x" in pos and "y" in pos:
                g.positions[name] = {"x": float(pos["x"]), "y": float(pos["y"])}
        for e in edges:
            if not isinstance(e, dict):
                raise GraphError("Each edge must be an object {u, v, weight}.", "invalid_json")
            g.add_edge(e.get("u"), e.get("v"), e.get("weight"),
                       propagation_delay_ms=e.get("propagation_delay_ms", 1.0),
                       capacity_mbps=e.get("capacity_mbps", 10.0),
                       loss_probability=e.get("loss_probability", 0.0),
                       queue_capacity_packets=e.get("queue_capacity_packets", 20),
                       status=e.get("status", "up"))
        return g

    # -------------------------------------------------------- analysis
    def handshake(self) -> dict[str, Any]:
        total = sum(self.degree(n) for n in self.adj)
        e = len(self.edges())
        return {"degree_sum": total, "twice_edges": 2 * e, "holds": total == 2 * e}

    def components(self) -> list[list[str]]:
        seen: set[str] = set()
        comps = []
        for start in self.adj:
            if start in seen:
                continue
            comp, q = [], deque([start])
            seen.add(start)
            while q:
                u = q.popleft()
                comp.append(u)
                for v in self.neighbors(u):
                    if v not in seen:
                        seen.add(v)
                        q.append(v)
            comps.append(comp)
        return comps

    def is_connected(self) -> bool:
        return len(self.adj) > 0 and len(self.components()) == 1

    def operational_analysis(self) -> dict[str, Any]:
        """Return connectivity using only currently-up nodes and links.

        Structural graph theory methods intentionally continue to inspect the full
        stored graph; this view is the operational subset for failure-aware analysis.
        """
        active_nodes = {
            node for node in self.adj
            if self.node_properties.get(node, {}).get("status", "up") == "up"
        }
        active_adjacency: dict[str, list[str]] = {node: [] for node in active_nodes}
        active_edges = 0
        failed_edges: list[tuple[str, str]] = []
        unavailable_edges: list[tuple[str, str]] = []
        for u, v, _ in self.edges():
            props = self.get_edge_properties(u, v)
            if (u in active_nodes and v in active_nodes and props.get("status", "up") == "up"):
                active_adjacency[u].append(v)
                active_adjacency[v].append(u)
                active_edges += 1
            else:
                if props.get("status", "up") != "up":
                    failed_edges.append((u, v))
                if props.get("status", "up") != "up" or u not in active_nodes or v not in active_nodes:
                    unavailable_edges.append((u, v))
        degrees = {node: len(neighbors) for node, neighbors in active_adjacency.items()}
        seen: set[str] = set()
        components: list[list[str]] = []
        for start in sorted(active_nodes):
            if start in seen:
                continue
            component: list[str] = []
            queue = deque([start])
            seen.add(start)
            while queue:
                current = queue.popleft()
                component.append(current)
                for neighbor in sorted(active_adjacency[current]):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
        components.sort(key=lambda item: (-len(item), item[0] if item else ""))
        return {
            "active_node_count": len(active_nodes),
            "active_edge_count": active_edges,
            "failed_nodes": sorted(set(self.adj) - active_nodes),
            "failed_edges": [list(edge) for edge in sorted(set(failed_edges))],
            "unavailable_edges": [list(edge) for edge in sorted(set(unavailable_edges))],
            "degrees": degrees,
            "components": components,
            "component_count": len(components),
            "connected": len(active_nodes) > 0 and len(components) == 1,
            "isolated_nodes": sorted(node for node, degree in degrees.items() if degree == 0),
        }

    def euler(self) -> dict[str, Any]:
        """Eulerian classification: connectivity of non-isolated vertices + odd-degree count (about EDGES)."""
        non_isolated = [n for n in self.adj if self.degree(n) > 0]
        odd = [n for n in self.adj if self.degree(n) % 2 == 1]
        if not non_isolated:
            return {"classification": "none", "odd_vertices": [], "reason": "The graph has no edges, so there is no edge-trail to classify."}
        sub = [c for c in self.components() if any(self.degree(n) > 0 for n in c)]
        if len(sub) != 1:
            return {"classification": "none", "odd_vertices": odd, "reason": "Edges lie in more than one component, so no single trail can use every edge."}
        if len(odd) == 0:
            return {"classification": "circuit", "odd_vertices": odd, "reason": "Connected (ignoring isolated vertices) and every degree is even: Eulerian circuit exists."}
        if len(odd) == 2:
            return {"classification": "trail", "odd_vertices": odd, "reason": f"Exactly two odd-degree vertices ({odd[0]}, {odd[1]}): Eulerian trail exists, starting and ending at them."}
        return {"classification": "none", "odd_vertices": odd, "reason": f"{len(odd)} vertices have odd degree; an Eulerian trail needs 0 or 2."}

    def hamiltonian(self, cycle: bool) -> dict[str, Any]:
        """Backtracking search over VERTICES. Guarded: factorial worst case."""
        n = len(self.adj)
        if n > MAX_HAMILTONIAN_NODES:
            raise GraphError(
                f"Hamiltonian search is guarded to at most {MAX_HAMILTONIAN_NODES} nodes (graph has {n}); worst case is factorial.",
                "size_guard",
                422,
            )
        kind = "cycle" if cycle else "path"
        if n == 0:
            return {"kind": kind, "exists": False, "sequence": None, "reason": "Empty graph."}
        order = sorted(self.adj)
        if n == 1:
            return {"kind": kind, "exists": not cycle, "sequence": order if not cycle else None, "reason": "Single vertex."}
        result: list[str] | None = None

        def extend(path: list[str], used: set[str]) -> bool:
            nonlocal result
            if len(path) == n:
                if cycle and not self.has_edge(path[-1], path[0]):
                    return False
                result = list(path) + ([path[0]] if cycle else [])
                return True
            for nb in self.neighbors(path[-1]):
                if nb not in used:
                    used.add(nb)
                    path.append(nb)
                    if extend(path, used):
                        return True
                    path.pop()
                    used.discard(nb)
            return False

        starts = order[:1] if cycle else order
        if cycle and n < 3:
            return {"kind": kind, "exists": False, "sequence": None, "reason": "A cycle needs at least 3 vertices."}
        for s in starts:
            if extend([s], {s}):
                break
        return {
            "kind": kind,
            "exists": result is not None,
            "sequence": result,
            "reason": "Found by backtracking." if result else "Exhaustive backtracking found none.",
        }

    def greedy_coloring(self) -> dict[str, Any]:
        """Greedy: each vertex (insertion order) gets the smallest colour unused by its neighbours."""
        colors: dict[str, int] = {}
        for u in self.adj:
            used = {colors[v] for v in self.adj[u] if v in colors}
            c = 0
            while c in used:
                c += 1
            colors[u] = c
        valid = all(colors[u] != colors[v] for u, v, _ in self.edges())
        return {
            "colors": colors,
            "num_colors": (max(colors.values()) + 1) if colors else 0,
            "valid": valid,
            "note": "Greedy colouring is valid but not necessarily minimal (it may use more colours than the chromatic number).",
        }

    def analysis(self) -> dict[str, Any]:
        comps = self.components()
        return {
            "node_count": len(self.adj),
            "edge_count": len(self.edges()),
            "degrees": {n: self.degree(n) for n in self.adj},
            "handshake": self.handshake(),
            "components": comps,
            "component_count": len(comps),
            "connected": self.is_connected(),
            "isolated_nodes": [n for n in self.adj if self.degree(n) == 0],
            "euler": self.euler(),
            "adjacency_list": self.adjacency_list(),
            "adjacency_matrix": self.adjacency_matrix(),
        }

    # ---------------------------------------------- simple path counting
    def count_simple_paths(self, source: str, target: str) -> int:
        self.require(source)
        self.require(target)
        if len(self.adj) > MAX_PATH_COUNT_NODES:
            raise GraphError(
                f"Simple-path counting is guarded to at most {MAX_PATH_COUNT_NODES} nodes (graph has {len(self.adj)}).",
                "size_guard",
                422,
            )
        if source == target:
            return 1
        count = 0

        def walk(u: str, seen: set[str]) -> None:
            nonlocal count
            if u == target:
                count += 1
                return
            for v in self.adj[u]:
                if v not in seen:
                    seen.add(v)
                    walk(v, seen)
                    seen.discard(v)

        walk(source, {source})
        return count

    def count_walks_exact(self, source: str, target: str, length: int) -> int:
        """Exact number of walks of a given length = entry (source,target) of A^length (DP over steps)."""
        self.require(source)
        self.require(target)
        if length < 0 or length > 1000:
            raise GraphError("Walk length must be between 0 and 1000.", "invalid_input")
        counts = {n: 0 for n in self.adj}
        counts[source] = 1
        for _ in range(length):
            nxt = {n: 0 for n in self.adj}
            for u, c in counts.items():
                if c:
                    for v in self.adj[u]:
                        nxt[v] += c
            counts = nxt
        return counts[target]


# =====================================================================
# Traversal / routing traces. Each trace step is a full snapshot so the
# frontend can replay it without recomputing anything.
# =====================================================================

def _dist_view(dist: dict[str, float]) -> dict[str, float | None]:
    return {k: (None if v == math.inf else v) for k, v in dist.items()}


def bfs_trace(g: Graph, source: str, target: str | None = None) -> dict[str, Any]:
    g.require(source)
    if target is not None:
        g.require(target)
    discovered = [source]
    seen = {source}
    pred: dict[str, str | None] = {source: None}
    queue = deque([source])
    order: list[str] = []
    steps: list[dict[str, Any]] = []

    def snap(kind: str, message: str, current: str | None = None, edge: tuple[str, str] | None = None, **extra: Any) -> None:
        steps.append({
            "index": len(steps), "kind": kind, "message": message, "current": current,
            "edge": list(edge) if edge else None, "visited": list(discovered), "processed": list(order),
            "frontier": list(queue), "frontier_type": "queue", **extra,
        })

    snap("init", f"Enqueue source {source}.", source)
    found = False
    while queue:
        u = queue.popleft()
        order.append(u)
        snap("dequeue", f"Dequeue {u} and process it.", u)
        if target is not None and u == target:
            found = True
            snap("found", f"Target {target} reached.", u)
            break
        for v in g.neighbors(u):
            if v not in seen:
                seen.add(v)
                discovered.append(v)
                pred[v] = u
                queue.append(v)
                snap("examine", f"Edge {u}-{v}: {v} is new, enqueue it.", u, (u, v), discovered_new=True)
            else:
                snap("examine", f"Edge {u}-{v}: {v} already discovered, skip.", u, (u, v), discovered_new=False)
    path = _build_path(pred, target) if found else None
    return {"algorithm": "bfs", "source": source, "target": target, "traversal_order": order,
            "steps": steps, "found": found if target is not None else None, "path": path,
            "predecessors": pred}


def dfs_trace(g: Graph, source: str, target: str | None = None) -> dict[str, Any]:
    g.require(source)
    if target is not None:
        g.require(target)
    visited = {source}
    order = [source]
    pred: dict[str, str | None] = {source: None}
    stack: list[tuple[str, Iterable[str]]] = [(source, iter(g.neighbors(source)))]
    steps: list[dict[str, Any]] = []

    def snap(kind: str, message: str, current: str | None = None, edge: tuple[str, str] | None = None, **extra: Any) -> None:
        steps.append({
            "index": len(steps), "kind": kind, "message": message, "current": current,
            "edge": list(edge) if edge else None, "visited": list(order), "processed": list(order),
            "frontier": [n for n, _ in stack], "frontier_type": "stack", **extra,
        })

    snap("init", f"Push source {source} on the stack.", source)
    found = target is not None and source == target
    if found:
        snap("found", f"Target {target} is the source.", source)
    while stack and not found:
        node, it = stack[-1]
        nb = next(it, None)  # type: ignore[arg-type]
        if nb is None:
            stack.pop()
            back = stack[-1][0] if stack else None
            snap("backtrack", f"{node} has no unvisited neighbours; backtrack" + (f" to {back}." if back else "."), back or node, (node, back) if back else None)
            continue
        if nb in visited:
            snap("examine", f"Edge {node}-{nb}: {nb} already visited, skip.", node, (node, nb), discovered_new=False)
            continue
        visited.add(nb)
        pred[nb] = node
        order.append(nb)
        stack.append((nb, iter(g.neighbors(nb))))
        snap("visit", f"Edge {node}-{nb}: visit {nb}, push on the stack.", nb, (node, nb), discovered_new=True)
        if target is not None and nb == target:
            found = True
            snap("found", f"Target {target} reached.", nb)
    path = _build_path(pred, target) if found else None
    return {"algorithm": "dfs", "source": source, "target": target, "traversal_order": order,
            "steps": steps, "found": found if target is not None else None, "path": path,
            "predecessors": pred}


def dijkstra_trace(g: Graph, source: str, target: str | None = None) -> dict[str, Any]:
    g.require(source)
    if target is not None:
        g.require(target)
    for u, v, w in g.edges():
        if w < 0:
            raise GraphError("Negative edge weight found; Dijkstra requires non-negative weights.", "negative_weight")
    dist = {n: math.inf for n in g.adj}
    dist[source] = 0.0
    pred: dict[str, str | None] = {source: None}
    heap: list[tuple[float, str]] = [(0.0, source)]
    settled: list[str] = []
    settled_set: set[str] = set()
    steps: list[dict[str, Any]] = []

    def frontier() -> list[list[Any]]:
        nodes = {n for _, n in heap if n not in settled_set}
        return sorted([[n, dist[n]] for n in nodes], key=lambda p: (p[1], p[0]))

    def snap(kind: str, message: str, current: str | None = None, edge: tuple[str, str] | None = None, **extra: Any) -> None:
        steps.append({
            "index": len(steps), "kind": kind, "message": message, "current": current,
            "edge": list(edge) if edge else None,
            "visited": [n for n in g.adj if dist[n] != math.inf], "processed": list(settled),
            "frontier": frontier(), "frontier_type": "priority_queue",
            "distances": _dist_view(dist), "predecessors": dict(pred), **extra,
        })

    snap("init", f"Distance({source}) = 0; all others = infinity.", source)
    found = False
    while heap:
        d, u = heapq.heappop(heap)
        if u in settled_set:
            continue
        settled_set.add(u)
        settled.append(u)
        snap("settle", f"Settle {u} with final distance {d:g}.", u)
        if target is not None and u == target:
            found = True
            snap("found", f"Target {target} settled with cost {d:g}.", u)
            break
        for v in g.neighbors(u):
            if v in settled_set:
                continue
            nd = d + g.adj[u][v]
            if nd < dist[v]:
                old = dist[v]
                dist[v] = nd
                pred[v] = u
                heapq.heappush(heap, (nd, v))
                was = "inf" if old == math.inf else f"{old:g}"
                snap("relax", f"Edge {u}-{v}: {d:g}+{g.adj[u][v]:g}={nd:g} < {was}; update distance and predecessor.", u, (u, v), improved=True)
            else:
                snap("relax", f"Edge {u}-{v}: {d:g}+{g.adj[u][v]:g}={nd:g} is not better than {dist[v]:g}; keep.", u, (u, v), improved=False)
    path = _build_path(pred, target) if found else None
    return {"algorithm": "dijkstra", "source": source, "target": target, "traversal_order": settled,
            "steps": steps, "found": found if target is not None else None, "path": path,
            "predecessors": pred, "distances": _dist_view(dist)}


def _build_path(pred: dict[str, str | None], target: str | None) -> list[str] | None:
    if target is None or target not in pred:
        return None
    path, cur = [], target
    while cur is not None:
        path.append(cur)
        cur = pred[cur]
    return path[::-1]


ROUTE_LABELS = {
    "bfs": "Minimum-hop path (unweighted interpretation; weights ignored)",
    "dfs": "DFS-found path (not guaranteed shortest in hops or cost)",
    "dijkstra": "Minimum-cost path (non-negative weights)",
}


def compute_route(g: Graph, algorithm: str, source: str, target: str) -> dict[str, Any]:
    fn = {"bfs": bfs_trace, "dfs": dfs_trace, "dijkstra": dijkstra_trace}.get(algorithm)
    if fn is None:
        raise GraphError(f"Unknown algorithm '{algorithm}'. Use bfs, dfs or dijkstra.", "unknown_algorithm", 404)
    trace = fn(g, source, target)
    path = trace["path"]
    result = {
        "algorithm": algorithm, "source": source, "target": target, "found": bool(trace["found"]),
        "path": path, "hops": (len(path) - 1) if path else None,
        "cost": g.path_cost(path) if path else None,
        "label": ROUTE_LABELS[algorithm], "trace": trace["steps"],
        "traversal_order": trace["traversal_order"],
        "message": (f"{ROUTE_LABELS[algorithm]}: {' -> '.join(path)}" if path
                    else f"No route exists from {source} to {target}."),
    }
    return result


# ---------------------------------------------------------------- demo graph
DEMO_NODES = {
    "Main Gate": (40, 250), "Library": (260, 60), "Administration Block": (260, 250),
    "Cafeteria": (260, 440), "Computer Lab": (500, 60), "Hostel": (500, 340),
    "Data Center": (730, 230), "Research Lab": (730, 60),
}
DEMO_EDGES = [
    ("Main Gate", "Library", 4), ("Main Gate", "Administration Block", 2), ("Main Gate", "Cafeteria", 7),
    ("Library", "Computer Lab", 3), ("Library", "Administration Block", 5),
    ("Administration Block", "Hostel", 3), ("Administration Block", "Cafeteria", 6),
    ("Cafeteria", "Hostel", 2), ("Cafeteria", "Data Center", 5),
    ("Computer Lab", "Data Center", 2), ("Computer Lab", "Research Lab", 4),
    ("Hostel", "Data Center", 9), ("Data Center", "Research Lab", 3),
]
DEMO_PAIR = ("Main Gate", "Data Center")  # BFS: 2 hops cost 12; Dijkstra: 3 hops cost 9


def demo_graph() -> Graph:
    g = Graph()
    for name, (x, y) in DEMO_NODES.items():
        g.add_node(name, x, y)
    for u, v, w in DEMO_EDGES:
        g.add_edge(u, v, w)
    return g


def sample_graph(n: int, seed: int | None = None) -> Graph:
    """Random connected sample graph with simulated weights 1-10."""
    import random

    if n < 2 or n > 20:
        raise GraphError("Sample size must be between 2 and 20 nodes.", "invalid_input")
    rnd = random.Random(seed)
    g = Graph()
    names = [f"R{i + 1}" for i in range(n)]
    for i, name in enumerate(names):
        ang = 2 * math.pi * i / n
        g.add_node(name, 400 + 300 * math.cos(ang), 260 + 220 * math.sin(ang))
    for i in range(1, n):  # spanning tree keeps it connected
        g.add_edge(names[i], names[rnd.randrange(i)], rnd.randint(1, 10))
    extra = max(1, n // 2)
    for _ in range(extra * 3):
        a, b = rnd.sample(names, 2)
        if not g.has_edge(a, b) and extra > 0:
            g.add_edge(a, b, rnd.randint(1, 10))
            extra -= 1
    return g
