"""Reproducible, local discrete-event network simulation and experiment persistence.

The simulator is an empirical model, not a packet-level implementation of a real network stack.
See docs/SIMULATION_MODEL.md for event ordering, queueing and failure assumptions.
"""
from __future__ import annotations

import heapq
import hashlib
import json
import math
import platform
import random
import sqlite3
import statistics
import sys
import time
import uuid
from importlib.metadata import PackageNotFoundError, version as package_version
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .graph import Graph, GraphError
from .packet_security import Ed25519Identity, create_signed_packet, verify_signed_packet

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "irsd_research.sqlite3"
APP_VERSION = "2.0.0-research"
SUPPORTED_ALGORITHMS = {"bfs", "dijkstra_static", "dijkstra_dynamic"}


def _edge_key(u: str, v: str) -> tuple[str, str]:
    return (u, v) if u <= v else (v, u)


def generate_topology(family: str, node_count: int, seed: int) -> Graph:
    """Generate a deterministic undirected topology from standard graph families."""
    if family == "current":
        raise ValueError("The current topology must be supplied by the caller.")
    if not 2 <= node_count <= 100:
        raise ValueError("Generated topology node count must be between 2 and 100.")
    rng = random.Random(seed)
    graph = Graph()
    names = [f"N{i + 1}" for i in range(node_count)]
    for i, name in enumerate(names):
        angle = 2 * math.pi * i / node_count
        graph.add_node(name, 450 + 330 * math.cos(angle), 280 + 220 * math.sin(angle))

    pairs: set[tuple[int, int]] = set()
    if family == "erdos_renyi":
        p = min(1.0, max(0.0, 3.0 / max(1, node_count - 1)))
        for i in range(node_count):
            for j in range(i + 1, node_count):
                if rng.random() < p:
                    pairs.add((i, j))
        # Ensure a connected base via a spanning tree; additional random edges remain random.
        for i in range(1, node_count):
            pairs.add(tuple(sorted((i, rng.randrange(i)))))
    elif family == "small_world":
        k = min(4, node_count - 1)
        if k % 2:
            k -= 1
        k = max(2, k)
        for i in range(node_count):
            for offset in range(1, k // 2 + 1):
                j = (i + offset) % node_count
                pairs.add(tuple(sorted((i, j))))
        original = sorted(pairs)
        for i, j in original:
            if rng.random() < 0.25:
                candidates = [x for x in range(node_count) if x != i and tuple(sorted((i, x))) not in pairs]
                if candidates:
                    pairs.discard((i, j))
                    pairs.add(tuple(sorted((i, rng.choice(candidates)))))
    elif family == "scale_free":
        # Barabasi-Albert preferential attachment, m=2 where feasible.
        m = min(2, node_count - 1)
        for i in range(1, min(m + 1, node_count)):
            pairs.add((0, i))
        for i in range(m + 1, node_count):
            degrees = [sum(1 for a, b in pairs if a == j or b == j) for j in range(i)]
            chosen: set[int] = set()
            while len(chosen) < m:
                total = sum(max(1, d) for d in degrees)
                pick = rng.randrange(total)
                acc = 0
                for j, degree in enumerate(degrees):
                    acc += max(1, degree)
                    if pick < acc:
                        chosen.add(j)
                        break
            for j in chosen:
                pairs.add(tuple(sorted((i, j))))
    else:
        raise ValueError("Topology must be current, erdos_renyi, small_world or scale_free.")

    for i, j in sorted(pairs):
        graph.add_edge(names[i], names[j], round(rng.uniform(1, 10), 3),
                       propagation_delay_ms=round(rng.uniform(1, 15), 3),
                       capacity_mbps=100.0, loss_probability=0.0, queue_capacity_packets=20)
    return graph


def _available_neighbors(graph: Graph, node: str, failed_nodes: set[str], failed_edges: set[tuple[str, str]],
                         edge_counter: list[int] | None = None) -> list[str]:
    if node in failed_nodes or graph.node_properties.get(node, {}).get("status", "up") == "down":
        return []
    out = []
    for other in graph.neighbors(node):
        if edge_counter is not None:
            edge_counter[0] += 1
        key = _edge_key(node, other)
        props = graph.get_edge_properties(node, other)
        if other not in failed_nodes and graph.node_properties.get(other, {}).get("status", "up") != "down" \
                and key not in failed_edges and props.get("status", "up") == "up":
            out.append(other)
    return out


def _find_path(graph: Graph, source: str, target: str, algorithm: str,
               failed_nodes: set[str], failed_edges: set[tuple[str, str]],
               edge_counter: list[int] | None = None) -> list[str] | None:
    if source not in graph.adj or target not in graph.adj or source in failed_nodes or target in failed_nodes:
        return None
    if source == target:
        return [source]
    if algorithm == "bfs":
        queue = deque([source])
        parent: dict[str, str | None] = {source: None}
        while queue:
            u = queue.popleft()
            for v in _available_neighbors(graph, u, failed_nodes, failed_edges, edge_counter):
                if v not in parent:
                    parent[v] = u
                    if v == target:
                        path = [target]
                        cur = target
                        while parent[cur] is not None:
                            cur = parent[cur]  # type: ignore[assignment]
                            path.append(cur)
                        return path[::-1]
                    queue.append(v)
        return None
    heap: list[tuple[float, str]] = [(0.0, source)]
    dist = {source: 0.0}
    parent: dict[str, str | None] = {source: None}
    settled: set[str] = set()
    while heap:
        cost, u = heapq.heappop(heap)
        if u in settled:
            continue
        settled.add(u)
        if u == target:
            path = [target]
            cur = target
            while parent[cur] is not None:
                cur = parent[cur]  # type: ignore[assignment]
                path.append(cur)
            return path[::-1]
        for v in _available_neighbors(graph, u, failed_nodes, failed_edges, edge_counter):
            if v in settled:
                continue
            candidate = cost + graph.adj[u][v]
            if candidate < dist.get(v, math.inf):
                dist[v] = candidate
                parent[v] = u
                heapq.heappush(heap, (candidate, v))
    return None


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Evaluate the incomplete-beta continued fraction (Numerical Recipes form)."""
    max_iterations, epsilon, tiny = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iterations + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < epsilon:
            return h
    raise ArithmeticError("Incomplete-beta continued fraction did not converge.")


def _regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    if not (a > 0 and b > 0 and 0 <= x <= 1):
        raise ValueError("Invalid regularized incomplete-beta arguments.")
    if x == 0:
        return 0.0
    if x == 1:
        return 1.0
    log_factor = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    factor = math.exp(log_factor)
    if x < (a + 1.0) / (a + b + 2.0):
        return factor * _beta_continued_fraction(a, b, x) / a
    return 1.0 - factor * _beta_continued_fraction(b, a, 1.0 - x) / b


def _critical_t_975(df: int) -> float:
    """Numerically invert the Student-t CDF for a two-sided 95% interval."""
    if df < 1:
        raise ValueError("Degrees of freedom must be positive.")
    target_tail = 0.025
    a, b = df / 2.0, 0.5
    low, high = 0.0, 1.0
    while 0.5 * _regularized_incomplete_beta(a, b, df / (df + high * high)) > target_tail:
        high *= 2.0
    for _ in range(100):
        middle = (low + high) / 2.0
        tail = 0.5 * _regularized_incomplete_beta(a, b, df / (df + middle * middle))
        if tail > target_tail:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def summarize(values: list[float]) -> dict[str, Any]:
    n = len(values)
    if not n:
        return {"n": 0, "mean": None, "stddev": None, "median": None, "ci95": None}
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n >= 2 else 0.0
    half = _critical_t_975(n - 1) * sd / math.sqrt(n) if n >= 2 else None
    return {"n": n, "mean": mean, "stddev": sd, "median": statistics.median(values),
            "ci95": [mean - half, mean + half] if half is not None else None}


def paired_comparison(reference: list[dict[str, Any]], candidate: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    """Calculate paired candidate-reference differences using matching repetition indices."""
    def pair_key(run: dict[str, Any]) -> tuple[int, str]:
        seed_value = run.get("seed")
        return int(run["repetition"]), "" if seed_value is None else str(int(seed_value))

    left = {pair_key(x): x for x in reference}
    right = {pair_key(x): x for x in candidate}
    common = sorted(left.keys() & right.keys())
    deltas: list[float] = []
    for key in common:
        a, b = left[key].get("metrics", {}).get(metric), right[key].get("metrics", {}).get(metric)
        if a is not None and b is not None:
            deltas.append(float(b) - float(a))
    result = summarize(deltas)
    result["comparison"] = f"candidate - reference ({metric})"
    result["matched_repetitions"] = len(deltas)
    return result


def _traffic_times(config: dict[str, Any], rng: random.Random) -> list[float]:
    count = int(config["packet_count"])
    duration = float(config["duration_ms"])
    mode = config.get("traffic_model", "constant")
    if count == 1:
        return [0.0]
    if mode == "constant":
        return [i * duration / count for i in range(count)]
    if mode == "burst":
        burst_count = min(3, count)
        sizes = [count // burst_count + (1 if i < count % burst_count else 0) for i in range(burst_count)]
        times: list[float] = []
        for burst, size in enumerate(sizes):
            start = duration * burst / burst_count
            end = duration * (burst + 0.35) / burst_count
            for j in range(size):
                times.append(start if size == 1 else start + (end - start) * j / (size - 1))
        return sorted(times)
    if mode == "variable":
        # A deterministic Poisson-like arrival pattern normalized to the configured duration.
        gaps = [rng.expovariate(1.0) for _ in range(count)]
        total = sum(gaps)
        accum = 0.0
        out = []
        for gap in gaps:
            out.append(accum / total * duration)
            accum += gap
        return out
    raise ValueError("traffic_model must be constant, variable or burst.")


def simulate(graph_snapshot: dict[str, Any], config: dict[str, Any], *, algorithm: str,
             seed: int, repetition: int) -> dict[str, Any]:
    """Run one deterministic discrete-event simulation, returning metrics and provenance."""
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    graph = Graph.from_dict(graph_snapshot)
    if len(graph.nodes) < 2:
        raise ValueError("A simulation requires at least two nodes.")
    source = str(config.get("source") or graph.nodes[0])
    destination = str(config.get("destination") or graph.nodes[-1])
    graph.require(source)
    graph.require(destination)
    if source == destination:
        raise ValueError("Source and destination must be different.")
    packet_count = int(config["packet_count"])
    duration_ms = float(config["duration_ms"])
    packet_size_bytes = int(config["packet_size_bytes"])
    ttl = int(config["ttl"])
    if not 1 <= packet_count <= 5000:
        raise ValueError("packet_count must be between 1 and 5000.")
    if not 10 <= duration_ms <= 3_600_000:
        raise ValueError("duration_ms must be between 10 and 3,600,000.")
    if not 1 <= packet_size_bytes <= 65535:
        raise ValueError("packet_size_bytes must be between 1 and 65535.")
    if not 1 <= ttl <= 255:
        raise ValueError("ttl must be between 1 and 255.")

    # Optional per-packet profiles are used by the interactive Packet Transfer
    # page. The experiment runner leaves this unset and retains its uniform
    # packet-size workload. These are simulated traffic classes, not claims
    # about exact wire-level protocol formats.
    packet_profiles = config.get("packet_profiles")
    if packet_profiles is not None:
        if not isinstance(packet_profiles, list) or len(packet_profiles) != packet_count:
            raise ValueError("packet_profiles must contain exactly one profile per packet.")
        for profile in packet_profiles:
            if not isinstance(profile, dict):
                raise ValueError("Each packet profile must be an object.")
            size = int(profile.get("size_bytes", packet_size_bytes))
            if not 1 <= size <= 65535:
                raise ValueError("Each packet profile size_bytes must be between 1 and 65535.")
            if profile.get("scenario", "normal") not in {
                "normal", "drop", "duplicate", "tamper_payload", "tamper_route"
            }:
                raise ValueError("Packet scenario must be normal, drop, duplicate, tamper_payload or tamper_route.")

    include_trace = bool(config.get("include_trace", False))
    trace_events: list[dict[str, Any]] = []
    trace_truncated = False
    max_trace_events = 12000

    def emit(kind: str, at_ms: float, packet_id: int | None = None, *,
             packet: dict[str, Any] | None = None, from_node: str | None = None,
             to_node: str | None = None, hop: int | None = None,
             status: str | None = None, message: str = "") -> None:
        nonlocal trace_truncated
        if not include_trace:
            return
        if len(trace_events) >= max_trace_events:
            trace_truncated = True
            return
        trace_events.append({
            "index": len(trace_events), "at_ms": round(float(at_ms), 6),
            "kind": kind, "packet_id": packet_id,
            "packet_type": (packet or {}).get("packet_type"),
            "from_node": from_node, "to_node": to_node, "hop": hop,
            "status": status, "message": message,
        })

    rng = random.Random(seed)
    identity = Ed25519Identity.generate() if config.get("security_enabled", False) else None
    seen_nonces: set[str] = set()
    failed_nodes: set[str] = set()
    failed_edges: set[tuple[str, str]] = set()
    topology_version = 0
    last_failure_at: float | None = None
    failure_count = 0
    queues: dict[tuple[str, str], deque[int]] = defaultdict(deque)
    busy: set[tuple[str, str]] = set()
    in_service: dict[tuple[str, str], int] = {}
    edge_generations: dict[tuple[str, str], int] = defaultdict(int)
    packets: dict[int, dict[str, Any]] = {}
    terminal: list[dict[str, Any]] = []
    events: list[tuple[float, int, int, str, dict[str, Any]]] = []
    seq = 0
    metrics = {
        "generated_packets": packet_count, "network_delivered_packets": 0,
        "authenticated_packets": 0, "dropped_link_failure": 0, "dropped_node_failure": 0,
        "dropped_link_loss": 0, "dropped_queue_overflow": 0, "dropped_no_route": 0,
        "expired_packets": 0, "security_rejected_packets": 0, "queue_overflows": 0,
        "route_recalculations": 0, "edges_explored": 0, "hops_total": 0,
        "hops_attempted_total": 0, "transmitted_bytes": 0,
        "dropped_simulated": 0, "duplicate_copies": 0,
        "payload_tampered_packets": 0, "route_header_tampered_packets": 0,
    }
    route_recovery_ms: float | None = None
    security_sign_times: list[float] = []
    security_verify_times: list[float] = []
    events_processed = 0
    edge_counter = [0]

    def push(at: float, priority: int, kind: str, data: dict[str, Any]) -> None:
        nonlocal seq
        seq += 1
        heapq.heappush(events, (float(at), priority, seq, kind, data))

    # Freeze the time-zero forwarding entries for the selected destination at every node.
    # This is a destination-specific column of the single-destination experiment's routing table.
    base_router = "bfs" if algorithm == "bfs" else "dijkstra"
    static_routing_table = {
        node: _find_path(graph, node, destination, base_router, set(), set(), edge_counter)
        for node in graph.nodes
    }
    static_path = static_routing_table.get(source)

    failures = config.get("failures", []) or []
    occupied_intervals: dict[tuple[Any, ...], list[tuple[float, float]]] = defaultdict(list)
    for failure in failures:
        kind = failure.get("kind")
        if kind == "link":
            resource = ("link", *_edge_key(str(failure.get("u", "")), str(failure.get("v", ""))))
        elif kind == "node":
            resource = ("node", str(failure.get("node", "")))
        else:
            raise ValueError("Failure kind must be link or node.")
        start, end = float(failure.get("at_ms", 0)), float(failure.get("at_ms", 0)) + float(failure.get("duration_ms", 0))
        for old_start, old_end in occupied_intervals[resource]:
            if max(start, old_start) < min(end, old_end):
                raise ValueError(f"Overlapping failure windows are not supported for {resource}.")
        occupied_intervals[resource].append((start, end))
    for index, failure in enumerate(failures):
        kind = failure.get("kind")
        at = float(failure.get("at_ms", 0))
        duration = float(failure.get("duration_ms", 0))
        if at < 0 or at > duration_ms or duration <= 0:
            raise ValueError("Each failure must start within the traffic window and have positive duration_ms.")
        if kind == "link":
            u, v = str(failure.get("u", "")), str(failure.get("v", ""))
            if not graph.has_edge(u, v):
                raise ValueError(f"Failure schedule references unknown link {u}-{v}.")
            push(at, 0, "link_down", {"key": _edge_key(u, v), "index": index})
            push(at + duration, 0, "link_up", {"key": _edge_key(u, v), "index": index})
        elif kind == "node":
            node = str(failure.get("node", ""))
            graph.require(node)
            push(at, 0, "node_down", {"node": node, "index": index})
            push(at + duration, 0, "node_up", {"node": node, "index": index})
        else:
            raise ValueError("Failure kind must be link or node.")

    traffic_times = _traffic_times(config, rng)
    for packet_id, created_at in enumerate(traffic_times, 1):
        push(created_at, 2, "generate", {"packet_id": packet_id})

    tamper_rate = float(config.get("tamper_rate", 0.0))
    if not 0 <= tamper_rate <= 1:
        raise ValueError("tamper_rate must be between 0 and 1.")
    duplicate_rate = float(config.get("duplicate_rate", 0.0))
    if not 0 <= duplicate_rate <= 1:
        raise ValueError("duplicate_rate must be between 0 and 1.")
    generated_at_by_id = {i + 1: t for i, t in enumerate(traffic_times)}

    def finish_packet(packet_id: int, status: str, now: float, reason: str, *,
                      event_kind: str | None = None, from_node: str | None = None,
                      to_node: str | None = None, hop: int | None = None) -> None:
        packet = packets[packet_id]
        if packet.get("terminal"):
            return
        packet["terminal"] = True
        packet["status"] = status
        packet["finished_at_ms"] = now
        packet["reason"] = reason
        terminal.append(packet)
        if status in metrics:
            metrics[status] += 1
        current = packet.get("current")
        terminal_kind = event_kind or ("delivered" if status.startswith("delivered") else "dropped")
        emit(terminal_kind, now, packet_id, packet=packet,
             from_node=from_node if from_node is not None else current,
             to_node=to_node if to_node is not None else current,
             hop=hop if hop is not None else packet.get("hops"),
             status=status, message=reason)

    def choose_route(packet: dict[str, Any], now: float, force: bool = False) -> list[str] | None:
        nonlocal topology_version
        if algorithm == "dijkstra_static" or algorithm == "bfs":
            # Use only the route entry frozen at t=0 for the packet's current router.
            return static_routing_table.get(packet["current"])
        if force or packet.get("last_topology_version") != topology_version or not packet.get("current_path"):
            path = _find_path(graph, packet["current"], destination, "dijkstra", failed_nodes, failed_edges, edge_counter)
            had_previous_path = packet.get("current_path") is not None
            packet["last_topology_version"] = topology_version
            if packet.get("current_path") is not None or topology_version > 0:
                metrics["route_recalculations"] += 1
            if packet.get("current_path") != path and last_failure_at is not None:
                packet["rerouted_after_failure"] = True
            packet["current_path"] = path
            packet["route_cursor"] = 0
            emit("route_recalculated", now, packet["packet_id"], packet=packet,
                 from_node=packet["current"], to_node=(path[1] if path and len(path) > 1 else None),
                 hop=packet.get("hops"), status=("Rerouted" if had_previous_path else "Route selected") if path else "No route",
                 message=(f"Dynamic Dijkstra selected {' → '.join(path)}." if path else "No active route remains."))
            return path
        return packet.get("current_path")

    def start_next(key: tuple[str, str], now: float) -> None:
        if key in busy or not queues[key]:
            return
        u, v = key
        if _edge_key(u, v) in failed_edges or graph.get_edge_properties(u, v).get("status", "up") == "down" or u in failed_nodes or v in failed_nodes:
            return
        packet_id = queues[key].popleft()
        packet = packets[packet_id]
        if packet.get("terminal"):
            start_next(key, now)
            return
        busy.add(key)
        in_service[key] = packet_id
        props = graph.get_edge_properties(u, v)
        serialization_ms = int(packet["size_bytes"]) * 8 / (float(props["capacity_mbps"]) * 1_000_000) * 1000
        packet["queue_wait_ms"] += max(0.0, now - packet.pop("queued_at_ms", now))
        packet["serialization_ms"] += serialization_ms
        # A per-packet "drop" is an in-flight fault, not a packet that is
        # excluded before dispatch. Match the original IRSD behaviour by
        # choosing a middle route edge, then let the packet serialize and
        # propagate on that edge before recording the loss.
        forced_drop = (
            packet.get("scenario") == "drop"
            and not packet.get("scenario_applied")
            and packet.get("hops", 0) >= packet.get("drop_after_hops", 0)
        )
        loss_status: str | None = None
        loss_reason = ""
        if forced_drop:
            loss_status = "dropped_simulated"
            loss_reason = f"Packet {packet_id} was transmitted on {u} → {v} and lost on that link (configured packet-loss scenario)."
        else:
            loss_material = f"{seed}|{packet_id}|{u}|{v}|{packet['hops']}".encode()
            loss_draw = int.from_bytes(hashlib.sha256(loss_material).digest()[:8], "big") / 2**64
            if loss_draw < float(props.get("loss_probability", 0.0)):
                loss_status = "dropped_link_loss"
                loss_reason = f"Packet {packet_id} was transmitted on {u} → {v} and lost on that link (configured link loss probability)."
        packet.setdefault("edge_attempts", []).append({
            "from_node": u, "to_node": v, "started_at_ms": round(float(now), 6),
            "status": "transmitting", "hop": packet.get("hops", 0) + 1,
        })
        metrics["hops_attempted_total"] += 1
        emit("transmitting", now, packet_id, packet=packet, from_node=u, to_node=v,
             hop=packet["hops"] + 1, status="In transit",
             message=f"{packet.get('packet_type', 'data').upper()} packet {packet_id} is transmitting on {u} → {v}." +
                     (" A packet-loss fault is scheduled on this edge." if loss_status else ""))
        generation = edge_generations[key]
        push(now + serialization_ms, 3, "transmit_complete", {
            "packet_id": packet_id, "u": u, "v": v, "generation": generation,
            "propagation_delay_ms": float(props["propagation_delay_ms"]),
            "loss_status": loss_status, "loss_reason": loss_reason,
        })

    def forward(packet_id: int, now: float, force_recompute: bool = False) -> None:
        packet = packets[packet_id]
        if packet.get("terminal"):
            return
        current = packet["current"]
        if current in failed_nodes:
            finish_packet(packet_id, "dropped_node_failure", now, f"Current node {current} is failed.")
            return
        if packet["hops"] >= ttl:
            finish_packet(packet_id, "expired_packets", now, "TTL exhausted before reaching destination.")
            return
        path = choose_route(packet, now, force_recompute)
        if not path or current not in path:
            finish_packet(packet_id, "dropped_no_route", now, "No active route to the destination.")
            return
        cursor = path.index(current)
        if cursor >= len(path) - 1:
            if current == destination:
                arrive_destination(packet_id, now)
            else:
                finish_packet(packet_id, "dropped_no_route", now, "Route does not lead to destination.")
            return
        nxt = path[cursor + 1]
        edge_key = _edge_key(current, nxt)
        key = (current, nxt)  # transmission queues are per direction (full-duplex link model)
        if edge_key in failed_edges or nxt in failed_nodes or graph.get_edge_properties(current, nxt).get("status", "up") == "down":
            if algorithm == "dijkstra_dynamic":
                forward(packet_id, now, True)
            else:
                finish_packet(packet_id, "dropped_link_failure" if nxt not in failed_nodes else "dropped_node_failure",
                              now, f"Frozen route encountered unavailable hop {current}-{nxt}.")
            return
        props = graph.get_edge_properties(current, nxt)
        capacity = int(props.get("queue_capacity_packets", 20))
        occupancy = len(queues[key]) + (1 if key in busy else 0)
        if occupancy >= capacity:
            metrics["queue_overflows"] += 1
            finish_packet(packet_id, "dropped_queue_overflow", now, f"Queue on {current}-{nxt} is full.")
            return
        packet["queued_at_ms"] = now
        queues[key].append(packet_id)
        emit("queued", now, packet_id, packet=packet, from_node=current, to_node=nxt,
             hop=packet["hops"] + 1, status="Queued",
             message=f"Packet {packet_id} entered the FIFO queue for {current} → {nxt}.")
        start_next(key, now)

    def arrive_destination(packet_id: int, now: float) -> None:
        packet = packets[packet_id]
        if packet.get("terminal"):
            return
        metrics["network_delivered_packets"] += 1
        packet["network_delivered"] = True
        packet["delivered_at_ms"] = now
        if packet.get("rerouted_after_failure") and last_failure_at is not None and route_recovery_ms is None:
            # Captured after the outer scope sets route_recovery_ms in the event loop below.
            packet["recovery_candidate_ms"] = max(0.0, now - last_failure_at)
        if identity is not None:
            signed = packet["signed_packet"]
            payload = packet["payload"]
            packet_id_for_draw = packet["packet_id"]
            tamper_material = f"{seed}|{packet_id_for_draw}|tamper".encode()
            tamper_draw = int.from_bytes(hashlib.sha256(tamper_material).digest()[:8], "big") / 2**64
            if tamper_draw < tamper_rate:
                payload = payload + "[tampered]"
            verification = verify_signed_packet(signed, payload, arrival_at_ms=now,
                                                seen_nonces=seen_nonces)
            security_verify_times.append(float(verification["verification_time_ms"]))
            packet["security"] = verification
            if verification["valid"]:
                metrics["authenticated_packets"] += 1
                finish_packet(packet_id, "delivered", now, "Network delivery and authentication succeeded.")
            else:
                # finish_packet accounts for terminal-state counters exactly once.
                finish_packet(packet_id, "security_rejected_packets", now, verification["reason"])
        else:
            if packet.get("payload_modified"):
                finish_packet(packet_id, "delivered_payload_modified", now,
                              "Packet reached the destination, but its payload was modified in transit.")
            elif packet.get("route_header_modified"):
                finish_packet(packet_id, "delivered_route_header_modified", now,
                              "Packet reached the destination, but its route metadata was modified in transit.")
            else:
                finish_packet(packet_id, "delivered", now, "Packet reached the destination successfully.")
        if packet.get("scenario") == "duplicate":
            packet["duplicate_copies"] = int(packet.get("duplicate_copies", 0)) + 1
            metrics["duplicate_copies"] += 1
            emit("duplicate", now, packet_id, packet=packet, from_node=destination,
                 to_node=destination, hop=packet.get("hops"), status="Duplicate copy",
                 message=f"A duplicate copy of packet {packet_id} was observed at {destination}; it is not counted as a second unique delivery.")
        duplicate_draw = int.from_bytes(hashlib.sha256(f"{seed}|{packet_id}|duplicate".encode()).digest()[:8], "big") / 2**64
        if duplicate_draw < duplicate_rate and identity is not None:
            # Duplicate arrival reuses the same nonce and is rejected by the replay cache.
            replay = verify_signed_packet(packet["signed_packet"], packet["payload"],
                                          arrival_at_ms=now + 0.001, seen_nonces=seen_nonces)
            security_verify_times.append(float(replay["verification_time_ms"]))
            if replay["status"] == "replay_rejected":
                metrics.setdefault("replay_rejected_duplicates", 0)
                metrics["replay_rejected_duplicates"] += 1

    while events:
        now, _, _, kind, data = heapq.heappop(events)
        events_processed += 1
        if events_processed > 1_000_000:
            raise ValueError("Simulation exceeded the one-million-event safety limit.")
        if kind == "link_down":
            key = data["key"]
            emit("link_down", now, from_node=key[0], to_node=key[1], status="Link failed",
                 message=f"Link {key[0]} ↔ {key[1]} is now unavailable.")
            failed_edges.add(key)
            edge_generations[(key[0], key[1])] += 1
            edge_generations[(key[1], key[0])] += 1
            topology_version += 1
            failure_count += 1
            last_failure_at = now if last_failure_at is None else min(last_failure_at, now)
            # Packets waiting behind a failed link are immediately rerouted by the dynamic strategy;
            # the static strategy keeps its frozen next hop and records the failure.
            for u, v in (key, (key[1], key[0])):
                direction = (u, v)
                pending = list(queues[direction])
                queues[direction].clear()
                for packet_id in pending:
                    packet = packets[packet_id]
                    if algorithm == "dijkstra_dynamic":
                        packet["current"] = u
                        forward(packet_id, now, True)
                    else:
                        finish_packet(packet_id, "dropped_link_failure", now,
                                      f"Packet was queued on failed link {u}-{v}; static route was not recalculated.")
        elif kind == "link_up":
            key = data["key"]
            emit("link_up", now, from_node=key[0], to_node=key[1], status="Link restored",
                 message=f"Link {key[0]} ↔ {key[1]} has been restored.")
            failed_edges.discard(key)
            edge_generations[(key[0], key[1])] += 1
            edge_generations[(key[1], key[0])] += 1
            topology_version += 1
            start_next((key[0], key[1]), now)
            start_next((key[1], key[0]), now)
        elif kind == "node_down":
            failed_node = data["node"]
            emit("node_down", now, from_node=failed_node, to_node=failed_node,
                 status="Node failed", message=f"Node {failed_node} is now unavailable.")
            failed_nodes.add(failed_node)
            topology_version += 1
            failure_count += 1
            last_failure_at = now if last_failure_at is None else min(last_failure_at, now)
            for neighbor in graph.neighbors(failed_node):
                edge_generations[(failed_node, neighbor)] += 1
                edge_generations[(neighbor, failed_node)] += 1
                for u, v in ((neighbor, failed_node), (failed_node, neighbor)):
                    pending = list(queues[(u, v)])
                    queues[(u, v)].clear()
                    for packet_id in pending:
                        packet = packets[packet_id]
                        if algorithm == "dijkstra_dynamic" and packet["current"] == u:
                            forward(packet_id, now, True)
                        else:
                            finish_packet(packet_id, "dropped_node_failure", now,
                                          f"Packet was queued through failed node {failed_node}.")
        elif kind == "node_up":
            failed_nodes.discard(data["node"])
            emit("node_up", now, from_node=data["node"], to_node=data["node"],
                 status="Node restored", message=f"Node {data['node']} is available again.")
            topology_version += 1
        elif kind == "generate":
            packet_id = int(data["packet_id"])
            created_at = generated_at_by_id[packet_id]
            profile = packet_profiles[packet_id - 1] if packet_profiles is not None else {}
            packet_type = str(profile.get("packet_type", "data")).lower()
            packet_size = int(profile.get("size_bytes", packet_size_bytes))
            packet_payload = str(profile.get("payload", f"IRSD {packet_type.upper()} packet {packet_id}"))
            packet = {
                "packet_id": packet_id, "source": source, "destination": destination,
                "current": source, "generated_at_ms": created_at, "hops": 0, "ttl": ttl,
                "terminal": False, "status": "in_transit", "queue_wait_ms": 0.0,
                "serialization_ms": 0.0, "route_history": [], "rerouted_after_failure": False,
                "last_topology_version": None, "current_path": None, "static_path": static_path,
                "payload": packet_payload, "packet_type": packet_type, "size_bytes": packet_size,
                "scenario": profile.get("scenario", "normal"), "duplicate_copies": 0,
                "edge_attempts": [], "scenario_applied": False,
                # Same midpoint-edge selection used by the original packet
                # dispatcher: earlier hops complete, then this packet is lost
                # while traversing one of the route's links.
                "drop_after_hops": max(0, (len(static_path) - 2) // 2) if static_path else 0,
            }
            packets[packet_id] = packet
            packet["route_history"].append(source)
            emit("generated", now, packet_id, packet=packet, from_node=source, to_node=source,
                 hop=0, status="Created",
                 message=f"Created {packet_type.upper()} packet {packet_id} ({packet_size} bytes) at {source}.")
            if identity is not None:
                expires_at = created_at + float(config.get("packet_expiry_ms", duration_ms * 2))
                signed = create_signed_packet(identity, str(packet_id), source, destination,
                                              packet["payload"], created_at, expires_at)
                packet["signed_packet"] = signed
                security_sign_times.append(float(signed["signing_time_ms"]))
            if not static_path:
                finish_packet(packet_id, "dropped_no_route", now, "No initial path exists in the base topology.")
            else:
                forward(packet_id, now)
        elif kind == "transmit_complete":
            packet_id, u, v = int(data["packet_id"]), data["u"], data["v"]
            key = (u, v)
            edge_key = _edge_key(u, v)
            busy.discard(key)
            in_service.pop(key, None)
            packet = packets[packet_id]
            emit("serialization_complete", now, packet_id, packet=packet, from_node=u, to_node=v,
                 hop=packet["hops"] + 1, status="Transmitted",
                 message=f"Packet {packet_id} completed serialization on {u} → {v}.")
            metrics["transmitted_bytes"] += int(packet.get("size_bytes", packet_size_bytes))
            if packet.get("edge_attempts"):
                packet["edge_attempts"][-1]["status"] = "serialized"
                packet["edge_attempts"][-1]["serialized_at_ms"] = round(float(now), 6)
            failed_during_transmission = edge_generations[key] != int(data["generation"])
            is_down = edge_key in failed_edges or u in failed_nodes or v in failed_nodes
            if not packet.get("terminal"):
                if failed_during_transmission or is_down:
                    if algorithm == "dijkstra_dynamic":
                        packet["current"] = u
                        forward(packet_id, now, True)
                    else:
                        finish_packet(packet_id, "dropped_link_failure", now,
                                      f"Link {u}-{v} failed during transmission; static route was not recalculated.")
                elif data.get("loss_status"):
                    if data["loss_status"] == "dropped_simulated":
                        packet["scenario_applied"] = True
                    push(now + float(data["propagation_delay_ms"]), 4, "packet_loss", {
                        "packet_id": packet_id, "u": u, "v": v,
                        "generation": int(data["generation"]),
                        "loss_status": data["loss_status"], "loss_reason": data["loss_reason"],
                    })
                else:
                    packet["hops"] += 1
                    metrics["hops_total"] += 1
                    # One-shot per-packet fault injection on the first successfully
                    # serialized hop. The forwarding engine still selects the next
                    # hop; these scenarios alter the carried payload/metadata only.
                    if not packet.get("scenario_applied") and packet.get("scenario") in {"tamper_payload", "tamper_route"}:
                        packet["scenario_applied"] = True
                        if packet["scenario"] == "tamper_payload":
                            packet["payload"] = str(packet["payload"]) + " [CORRUPTED]"
                            packet["payload_modified"] = True
                            metrics["payload_tampered_packets"] += 1
                            emit("payload_tampered", now, packet_id, packet=packet, from_node=u, to_node=v,
                                 hop=packet["hops"], status="Payload modified",
                                 message=f"Packet {packet_id} payload was modified in transit on {u} → {v}.")
                        else:
                            packet["route_header_modified"] = True
                            metrics["route_header_tampered_packets"] += 1
                            emit("route_header_tampered", now, packet_id, packet=packet, from_node=u, to_node=v,
                                 hop=packet["hops"], status="Route metadata modified",
                                 message=f"Packet {packet_id} route metadata was altered in transit on {u} → {v}; simulator forwarding continues from router state.")
                    push(now + float(data["propagation_delay_ms"]), 4, "arrival", {"packet_id": packet_id, "node": v})
            start_next(key, now)
        elif kind == "packet_loss":
            packet_id, u, v = int(data["packet_id"]), data["u"], data["v"]
            packet = packets[packet_id]
            if packet.get("terminal"):
                continue
            # If a link fails while the serialized packet is propagating, the
            # final outcome is still loss on that in-flight edge, with the
            # more specific physical failure reason retained in the status.
            edge_failed_in_flight = (
                edge_generations[(u, v)] != int(data["generation"])
                or _edge_key(u, v) in failed_edges
                or u in failed_nodes or v in failed_nodes
            )
            if packet.get("edge_attempts"):
                packet["edge_attempts"][-1]["status"] = "lost"
                packet["edge_attempts"][-1]["lost_at_ms"] = round(float(now), 6)
            packet["lost_on_edge"] = {
                "from_node": u, "to_node": v, "hop": packet.get("hops", 0) + 1,
                "lost_at_ms": round(float(now), 6),
            }
            loss_status = "dropped_link_failure" if edge_failed_in_flight else data["loss_status"]
            reason = (f"Packet {packet_id} was in flight on {u} → {v} when the link failed; it did not reach {v}."
                      if edge_failed_in_flight else data["loss_reason"])
            finish_packet(packet_id, loss_status, now, reason,
                          event_kind="packet_lost_on_link", from_node=u, to_node=v,
                          hop=packet.get("hops", 0) + 1)
        elif kind == "arrival":
            packet_id, node = int(data["packet_id"]), data["node"]
            packet = packets[packet_id]
            if packet.get("terminal"):
                continue
            if node in failed_nodes:
                finish_packet(packet_id, "dropped_node_failure", now, f"Destination/intermediate node {node} failed before processing.")
                continue
            packet["current"] = node
            packet["route_history"].append(node)
            emit("hop_arrival", now, packet_id, packet=packet,
                 from_node=packet["route_history"][-2] if len(packet["route_history"]) > 1 else source,
                 to_node=node, hop=packet["hops"], status="Arrived at hop",
                 message=f"Packet {packet_id} reached {node} after hop {packet['hops']}.")
            if node == destination:
                arrive_destination(packet_id, now)
            else:
                forward(packet_id, now)

    # Route recovery is the first successful delivery of a packet whose route adapted after a failure.
    recovery_candidates = [p.get("recovery_candidate_ms") for p in terminal if p.get("recovery_candidate_ms") is not None]
    if recovery_candidates:
        route_recovery_ms = min(float(x) for x in recovery_candidates)

    generated = len(packets)
    delivered = sum(1 for p in terminal if p["status"] in {
        "delivered", "delivered_payload_modified", "delivered_route_header_modified", "security_rejected_packets"
    })
    authenticated = sum(1 for p in terminal if p["status"] == "delivered")
    latencies = [float(p["delivered_at_ms"] - p["generated_at_ms"]) for p in terminal if p.get("network_delivered")]
    completed_at = max((float(p.get("finished_at_ms", 0.0)) for p in terminal), default=duration_ms)
    measurement_window_ms = max(float(duration_ms), completed_at)
    delivered_bytes = sum(int(p.get("size_bytes", packet_size_bytes)) for p in terminal if p.get("network_delivered"))
    delivered_bits = delivered_bytes * 8
    metrics_out = {
        **metrics,
        "packet_delivery_ratio": delivered / generated if generated else 0.0,
        "packet_loss_ratio": (generated - delivered) / generated if generated else 0.0,
        "throughput_mbps": delivered_bits / (measurement_window_ms / 1000.0) / 1_000_000 if measurement_window_ms > 0 else 0.0,
        "mean_latency_ms": statistics.fmean(latencies) if latencies else None,
        "median_latency_ms": statistics.median(latencies) if latencies else None,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "route_recovery_ms": route_recovery_ms,
        "mean_signing_time_ms": statistics.fmean(security_sign_times) if security_sign_times else None,
        "mean_verification_time_ms": statistics.fmean(security_verify_times) if security_verify_times else None,
        "security_verification_enabled": identity is not None,
        "verification_success_rate": authenticated / delivered if identity is not None and delivered else None,
        "measurement_window_ms": measurement_window_ms,
        "simulation_clock_ms": completed_at,
        "events_processed": events_processed,
        "delivered_bytes": delivered_bytes,
        "edges_explored": edge_counter[0],
        "failure_events_applied": failure_count,
        "static_routing_table_entries": sum(path is not None for path in static_routing_table.values()),
        "total_latency_samples": len(latencies),
    }
    return {
        "algorithm": algorithm, "repetition": repetition, "seed": seed,
        "metrics": metrics_out,
        "packet_outcomes": [
            {"packet_id": p["packet_id"], "packet_type": p.get("packet_type", "data"),
             "size_bytes": int(p.get("size_bytes", packet_size_bytes)),
             "status": p["status"], "reason": p["reason"],
             "scenario": p.get("scenario", "normal"),
             "payload_modified": bool(p.get("payload_modified", False)),
             "route_header_modified": bool(p.get("route_header_modified", False)),
             "generated_at_ms": p["generated_at_ms"], "finished_at_ms": p.get("finished_at_ms"),
             "latency_ms": (float(p["finished_at_ms"] - p["generated_at_ms"]) if p.get("finished_at_ms") is not None else None),
             "hops": p["hops"], "route_history": p["route_history"],
             "attempted_hops": len(p.get("edge_attempts", [])),
             "edge_attempts": p.get("edge_attempts", []),
             "lost_on_edge": p.get("lost_on_edge"),
             "duplicate_copies": int(p.get("duplicate_copies", 0)),
             "security": p.get("security")}
            for p in sorted(terminal, key=lambda x: x["packet_id"])
        ],
        **({"trace_events": trace_events, "trace_truncated": trace_truncated} if include_trace else {}),
    }


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1))
    return ordered[index]


def _init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS experiment_runs (
            run_id TEXT PRIMARY KEY, comparison_id TEXT NOT NULL, algorithm TEXT NOT NULL,
            repetition INTEGER NOT NULL, seed INTEGER NOT NULL, created_at TEXT NOT NULL,
            config_json TEXT NOT NULL, topology_json TEXT NOT NULL, result_json TEXT NOT NULL,
            app_version TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_experiment_group ON experiment_runs(comparison_id, algorithm, repetition)")
        conn.execute("""CREATE TABLE IF NOT EXISTS experiment_packet_outcomes (
            run_id TEXT NOT NULL, packet_index INTEGER NOT NULL, packet_id TEXT NOT NULL,
            status TEXT NOT NULL, outcome_json TEXT NOT NULL,
            PRIMARY KEY(run_id, packet_index),
            FOREIGN KEY(run_id) REFERENCES experiment_runs(run_id) ON DELETE CASCADE
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_packet_outcomes_run ON experiment_packet_outcomes(run_id, packet_index)")


def persist_run(comparison_id: str, algorithm: str, repetition: int, seed: int,
                config: dict[str, Any], topology: dict[str, Any], result: dict[str, Any]) -> str:
    _init_db()
    run_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    stored_result = {key: value for key, value in result.items() if key != "packet_outcomes"}
    packet_outcomes = result.get("packet_outcomes", [])
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""INSERT INTO experiment_runs
        (run_id, comparison_id, algorithm, repetition, seed, created_at, config_json, topology_json, result_json, app_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, comparison_id, algorithm, repetition, seed, created_at,
         json.dumps(config, sort_keys=True), json.dumps(topology, sort_keys=True),
         json.dumps(stored_result, sort_keys=True), APP_VERSION))
        if packet_outcomes:
            conn.executemany("""INSERT INTO experiment_packet_outcomes
                (run_id, packet_index, packet_id, status, outcome_json) VALUES (?, ?, ?, ?, ?)""",
                [(run_id, index, str(outcome.get("packet_id", index)), str(outcome.get("status", "unknown")),
                  json.dumps(outcome, sort_keys=True)) for index, outcome in enumerate(packet_outcomes)])
    return run_id


def list_experiments(limit: int = 50) -> list[dict[str, Any]]:
    _init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT comparison_id, MIN(created_at), COUNT(*), MAX(app_version) FROM experiment_runs GROUP BY comparison_id ORDER BY MIN(created_at) DESC LIMIT ?", (limit,)).fetchall()
    return [{"comparison_id": r[0], "created_at": r[1], "run_count": r[2], "app_version": r[3]} for r in rows]


def get_experiment(comparison_id: str) -> dict[str, Any]:
    _init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT run_id, algorithm, repetition, seed, created_at, config_json, topology_json, result_json, app_version FROM experiment_runs WHERE comparison_id = ? ORDER BY algorithm, repetition", (comparison_id,)).fetchall()
    if not rows:
        raise KeyError(comparison_id)
    runs = []
    run_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result = json.loads(row[7])
        # Older development builds embedded outcomes in result_json. New runs store
        # them in a separate indexed table so comparison summaries stay lightweight.
        legacy_outcomes = result.pop("packet_outcomes", [])
        with sqlite3.connect(DB_PATH) as outcome_conn:
            normalized_count = outcome_conn.execute(
                "SELECT COUNT(*) FROM experiment_packet_outcomes WHERE run_id = ?", (row[0],)
            ).fetchone()[0]
        result["packet_outcome_count"] = normalized_count or len(legacy_outcomes)
        run_record = {
            "run_id": row[0], "algorithm": row[1], "repetition": row[2], "seed": row[3],
            "created_at": row[4], "config": json.loads(row[5]), "topology": json.loads(row[6]),
            "result": result, "app_version": row[8],
        }
        runs.append(run_record)
        run_groups[row[1]].append({
            "run_id": row[0], "algorithm": row[1], "repetition": row[2], "seed": row[3],
            "metrics": result.get("metrics", {}),
        })

    metric_keys = ["packet_delivery_ratio", "packet_loss_ratio", "throughput_mbps", "mean_latency_ms",
                   "median_latency_ms", "p95_latency_ms", "route_recovery_ms", "route_recalculations",
                   "mean_signing_time_ms", "mean_verification_time_ms"]
    summaries: dict[str, dict[str, Any]] = {}
    for algorithm, group in run_groups.items():
        summaries[algorithm] = {}
        for metric in metric_keys:
            values = [float(run["metrics"][metric]) for run in group if run["metrics"].get(metric) is not None]
            summaries[algorithm][metric] = summarize(values)
    algorithms = list(run_groups)
    reference = "dijkstra_static" if "dijkstra_static" in algorithms else algorithms[0]
    paired = {
        algorithm: {
            metric: paired_comparison(run_groups[reference], run_groups[algorithm], metric)
            for metric in ("packet_delivery_ratio", "throughput_mbps", "mean_latency_ms", "p95_latency_ms")
        }
        for algorithm in algorithms if algorithm != reference
    }
    return {
        "comparison_id": comparison_id,
        "runs": runs,
        "algorithms": algorithms,
        "repetitions": max((len(group) for group in run_groups.values()), default=0),
        "reference_algorithm": reference,
        "summaries": summaries,
        "paired_comparisons": paired,
        "runtime_provenance": runs[0]["config"].get("runtime_provenance", {}),
    }


def get_packet_outcomes(run_id: str, offset: int = 0, limit: int = 100) -> dict[str, Any]:
    """Fetch a bounded page of packet-level outcomes without loading all runs."""
    if offset < 0:
        raise ValueError("offset must be zero or greater.")
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500.")
    _init_db()
    with sqlite3.connect(DB_PATH) as conn:
        exists = conn.execute("SELECT 1 FROM experiment_runs WHERE run_id = ?", (run_id,)).fetchone()
        if not exists:
            raise KeyError(run_id)
        total = conn.execute("SELECT COUNT(*) FROM experiment_packet_outcomes WHERE run_id = ?", (run_id,)).fetchone()[0]
        rows = conn.execute("""SELECT outcome_json FROM experiment_packet_outcomes
            WHERE run_id = ? ORDER BY packet_index LIMIT ? OFFSET ?""", (run_id, limit, offset)).fetchall()
        packets = [json.loads(row[0]) for row in rows]
        # Read compatibility for runs created by earlier research builds.
        if total == 0:
            legacy = conn.execute("SELECT result_json FROM experiment_runs WHERE run_id = ?", (run_id,)).fetchone()
            embedded = json.loads(legacy[0]).get("packet_outcomes", []) if legacy else []
            total = len(embedded)
            packets = embedded[offset:offset + limit]
    return {"run_id": run_id, "offset": offset, "limit": limit, "total": total, "packets": packets}


def runtime_provenance() -> dict[str, Any]:
    """Capture versions that materially affect reproducibility and performance."""
    packages: dict[str, str] = {}
    for package in ("fastapi", "pydantic", "cryptography"):
        try:
            packages[package] = package_version(package)
        except PackageNotFoundError:
            packages[package] = "not-installed"
    return {
        "application_version": APP_VERSION,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": packages,
        "python_executable": sys.executable,
    }


def run_suite(topology: Graph, config: dict[str, Any], algorithms: list[str], repetitions: int) -> dict[str, Any]:
    if repetitions < 1 or repetitions > 30:
        raise ValueError("repetitions must be between 1 and 30.")
    if not algorithms or len(set(algorithms)) != len(algorithms):
        raise ValueError("Select one or more unique algorithms.")
    if int(config.get("packet_count", 0)) * repetitions * len(algorithms) > 60000:
        raise ValueError("This local synchronous runner is limited to 60,000 total simulated packets per comparison. Reduce packet_count, repetitions or algorithms.")
    invalid = set(algorithms) - SUPPORTED_ALGORITHMS
    if invalid:
        raise ValueError(f"Unsupported algorithms: {sorted(invalid)}")
    snapshot = topology.to_dict()
    provenance = runtime_provenance()
    saved_config = {**config, "runtime_provenance": provenance}
    base_seed = int(config.get("seed", 2026))
    comparison_id = uuid.uuid4().hex
    runs: dict[str, list[dict[str, Any]]] = {a: [] for a in algorithms}
    for repetition in range(repetitions):
        paired_seed = base_seed + repetition
        for algorithm in algorithms:
            result = simulate(snapshot, config, algorithm=algorithm, seed=paired_seed, repetition=repetition + 1)
            run_id = persist_run(comparison_id, algorithm, repetition + 1, paired_seed,
                                 saved_config, snapshot, result)
            response_result = {key: value for key, value in result.items() if key != "packet_outcomes"}
            response_result["packet_outcome_count"] = len(result.get("packet_outcomes", []))
            runs[algorithm].append({"run_id": run_id, **response_result})
    metric_keys = ["packet_delivery_ratio", "packet_loss_ratio", "throughput_mbps", "mean_latency_ms",
                   "median_latency_ms", "p95_latency_ms", "route_recovery_ms", "route_recalculations",
                   "mean_signing_time_ms", "mean_verification_time_ms"]
    summaries: dict[str, Any] = {}
    for algorithm, algorithm_runs in runs.items():
        summaries[algorithm] = {}
        for metric in metric_keys:
            vals = [float(r["metrics"][metric]) for r in algorithm_runs if r["metrics"].get(metric) is not None]
            summaries[algorithm][metric] = summarize(vals)
    reference = "dijkstra_static" if "dijkstra_static" in algorithms else algorithms[0]
    comparisons = {}
    for algorithm in algorithms:
        if algorithm == reference:
            continue
        comparisons[algorithm] = {
            metric: paired_comparison(runs[reference], runs[algorithm], metric)
            for metric in ["packet_delivery_ratio", "throughput_mbps", "mean_latency_ms", "p95_latency_ms"]
        }
    run_summaries = {
        algorithm: [
            {"run_id": run["run_id"], "algorithm": run["algorithm"], "repetition": run["repetition"],
             "seed": run["seed"], "metrics": run["metrics"], "packet_outcome_count": run["packet_outcome_count"]}
            for run in algorithm_runs
        ]
        for algorithm, algorithm_runs in runs.items()
    }
    return {
        "comparison_id": comparison_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "runtime_provenance": provenance,
        "topology": snapshot,
        "algorithms": algorithms,
        "repetitions": repetitions,
        "paired_seed_policy": "Same topology snapshot and seed (base_seed + repetition index) for every algorithm in a repetition.",
        "reference_algorithm": reference,
        "summaries": summaries,
        "paired_comparisons": comparisons,
        "runs": run_summaries,
        "limitations": [
            "This is a discrete-event educational simulator, not a real network stack or packet capture.",
            "Static Dijkstra freezes one forwarding entry per router for the selected destination at simulation start; it does not simulate all destinations concurrently.",
            "Link failures interrupt transmissions that overlap a failure event; propagation already in flight is not interrupted.",
            "Signing and verification timings are local wall-clock measurements and are environment-dependent.",
        ],
    }
