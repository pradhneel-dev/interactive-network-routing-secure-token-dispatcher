"""Packet creation, hop-by-hop dispatch simulation, destination verification and report.

LOCAL SIMULATION ONLY - no real packets are transmitted. Toy cryptography.
Packet loss (missing IDs) is detected separately from integrity/signature failures.
"""
from __future__ import annotations

import copy
import uuid
from typing import Any

from .graph import Graph, GraphError, ROUTE_LABELS
from .security import KeyRegistry, create_token, verify_token

MAX_PACKETS = 20
ROGUE = "Rogue-Router"


def validate_route(g: Graph, source: str, destination: str, route: list[str]) -> None:
    if len(route) < 2:
        raise GraphError("A route needs at least a source and a different destination.", "invalid_route")
    if route[0] != source or route[-1] != destination:
        raise GraphError("Route must start at the source and end at the destination.", "invalid_route")
    for n in route:
        g.require(n)
    for a, b in zip(route, route[1:]):
        if not g.has_edge(a, b):
            raise GraphError(f"Route is invalid for the current graph: no edge {a} - {b}.", "stale_route", 409)


def create_batch(g: Graph, registry: KeyRegistry, graph_version: int, source: str, destination: str,
                 route: list[str], algorithm: str, payload: str, count: int) -> dict[str, Any]:
    if source == destination:
        raise GraphError("Source and destination must differ.", "invalid_route")
    if not isinstance(payload, str) or not payload.strip():
        raise GraphError("Payload must not be empty.", "invalid_payload")
    if not 1 <= count <= MAX_PACKETS:
        raise GraphError(f"Packet count must be between 1 and {MAX_PACKETS}.", "invalid_count")
    if algorithm not in ROUTE_LABELS:
        raise GraphError("Unknown routing algorithm.", "unknown_algorithm", 404)
    validate_route(g, source, destination, route)
    batch_id = uuid.uuid4().hex[:6].upper()
    packets = []
    for seq in range(1, count + 1):
        pid = f"{batch_id}-{seq:03d}"
        body = payload.strip() if count == 1 else f"{payload.strip()} (part {seq}/{count})"
        packets.append({
            "packet_id": pid, "seq": seq, "source": source, "destination": destination, "route": list(route),
            "payload": body, "token": create_token(registry, pid, seq, source, destination, route, body),
            "status": "Created",
        })
    return {
        "batch_id": batch_id, "source": source, "destination": destination, "route": list(route),
        "algorithm": algorithm, "hops": len(route) - 1, "cost": g.path_cost(route),
        "graph_version": graph_version, "expected_ids": [p["packet_id"] for p in packets], "packets": packets,
        "warning": "Academic/toy cryptography - not production security.",
    }


def _tampered_route(route: list[str]) -> list[str]:
    return route[:-1] + [ROGUE] + route[-1:]


def dispatch(g: Graph, registry: KeyRegistry, batch: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    """Simulate transit for every packet, apply requested faults to the real packet copies, then verify."""
    route = batch["route"]
    validate_route(g, batch["source"], batch["destination"], route)  # raises 409 if graph changed
    pkts = batch["packets"]
    seqs = [p["seq"] for p in pkts]
    for key in ("drop_seqs", "tamper_payload_seqs", "tamper_route_seqs", "tamper_token_seqs", "duplicate_seqs"):
        bad = [s for s in options.get(key, []) if s not in seqs]
        if bad:
            raise GraphError(f"{key} contains unknown sequence numbers: {bad}.", "invalid_options")
    drop = set(options.get("drop_seqs", []))
    drop_count = options.get("drop_count", 0)
    if drop_count < 0 or drop_count > len(pkts):
        raise GraphError("drop_count must be between 0 and the number of packets.", "invalid_options")
    for s in reversed(seqs):  # configured count: drop the highest sequence numbers not already chosen
        if drop_count <= 0:
            break
        if s not in drop:
            drop.add(s)
            drop_count -= 1
    tp, tr, tt = set(options.get("tamper_payload_seqs", [])), set(options.get("tamper_route_seqs", [])), set(options.get("tamper_token_seqs", []))
    dup = set(options.get("duplicate_seqs", []))

    edge_idx = (len(route) - 2) // 2  # the link on which faults occur
    events: list[dict[str, Any]] = []
    arrivals: list[dict[str, Any]] = []

    def ev(kind: str, p: dict[str, Any], msg: str, frm: str | None = None, to: str | None = None,
           hop: int | None = None, status: str = "In transit") -> None:
        events.append({"index": len(events), "kind": kind, "packet_id": p["packet_id"], "seq": p["seq"],
                       "from": frm, "to": to, "hop": hop, "status": status, "message": msg})

    for p in pkts:
        s = p["seq"]
        received = copy.deepcopy(p)
        received.pop("status", None)
        ev("send", p, f"{p['packet_id']} created at {route[0]}; next hop {route[1]}.", route[0], route[0], 0, "Sent")
        lost = False
        for i in range(len(route) - 1):
            a, b = route[i], route[i + 1]
            if s in drop and i == edge_idx:
                ev("dropped", p, f"{p['packet_id']} was lost on link {a} -> {b} (simulated packet loss).", a, b, i + 1, "Lost")
                lost = True
                break
            nxt = f"next hop {route[i + 2]}" if i + 2 < len(route) else "destination reached"
            ev("hop", p, f"{p['packet_id']} hop {i + 1}/{len(route) - 1}: {a} -> {b} ({nxt}).", a, b, i + 1)
            if i == edge_idx:
                if s in tp:
                    received["payload"] += " [TAMPERED]"
                    ev("tamper", p, f"Payload of {p['packet_id']} was modified in transit near {b}.", a, b, i + 1, "Tampered")
                if s in tr:
                    received["route"] = _tampered_route(received["route"])
                    ev("tamper", p, f"Route header of {p['packet_id']} was altered in transit near {b}.", a, b, i + 1, "Tampered")
                if s in tt:
                    received["token"]["signature"] += 1
                    ev("tamper", p, f"Signature in the token of {p['packet_id']} was altered in transit near {b}.", a, b, i + 1, "Tampered")
        if lost:
            continue
        ev("arrived", p, f"{p['packet_id']} arrived at {route[-1]}.", route[-2], route[-1], len(route) - 1, "Arrived")
        arrivals.append(received)
        if s in dup:
            ev("duplicate", p, f"A duplicate copy of {p['packet_id']} arrived at {route[-1]}.", route[-2], route[-1], len(route) - 1, "Duplicate")
            arrivals.append(copy.deepcopy(received))

    results, report = receive(registry, batch, arrivals)
    status_by_id = {r["packet_id"]: r["status"] for r in results}
    for e in events:
        if e["kind"] == "arrived":
            e["final_status"] = status_by_id[e["packet_id"]]
    return {"events": events, "results": results, "report": report,
            "options_applied": {"dropped_seqs": sorted(drop), "tamper_payload_seqs": sorted(tp),
                                "tamper_route_seqs": sorted(tr), "tamper_token_seqs": sorted(tt), "duplicate_seqs": sorted(dup)}}


def receive(registry: KeyRegistry, batch: dict[str, Any], arrivals: list[dict[str, Any]]):
    """Destination receiver: loss check by ID comparison, then per-packet integrity/signature verification."""
    expected = batch["expected_ids"]
    seen: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for pkt in arrivals:
        pid = pkt["packet_id"]
        if pid in seen:
            duplicates.append(pid)
            continue
        header = {k: pkt[k] for k in ("packet_id", "seq", "source", "destination", "route")}
        seen[pid] = {"packet": pkt, "verify": verify_token(registry, pkt["token"], pkt["payload"], header)}
    by_seq = {p["packet_id"]: p["seq"] for p in batch["packets"]}
    missing = [pid for pid in expected if pid not in seen]
    results = []
    for pid in expected:
        seq = by_seq[pid]
        if pid in seen:
            v = seen[pid]["verify"]
            results.append({"packet_id": pid, "seq": seq, "received": True, "verified": v["valid"],
                            "status": v["status"], "checks": v["checks"], "reasons": v["reasons"],
                            "duplicate_copies": duplicates.count(pid),
                            "explanation": "; ".join(v["reasons"])})
        else:
            results.append({"packet_id": pid, "seq": seq, "received": False, "verified": False,
                            "status": "Lost/Missing", "checks": None, "reasons": ["Packet ID never arrived."],
                            "duplicate_copies": 0,
                            "explanation": "Expected ID was not received. A missing packet has no payload to hash, so this is packet loss, not an integrity failure."})
    return results, build_report(batch, results, missing, len(duplicates))


def build_report(batch: dict[str, Any], results: list[dict[str, Any]], missing: list[str], duplicates: int) -> dict[str, Any]:
    sent = len(batch["expected_ids"])
    count = lambda st: sum(1 for r in results if r["status"] == st)  # noqa: E731
    received = sum(1 for r in results if r["received"])
    verified = count("Delivered & Verified")
    return {
        "batch_id": batch["batch_id"], "algorithm": batch["algorithm"], "algorithm_label": ROUTE_LABELS[batch["algorithm"]],
        "route": batch["route"], "hops": batch["hops"], "cost": batch["cost"],
        "packets_sent": sent, "packets_received": received, "packets_lost": len(missing), "lost_ids": missing,
        "delivered_verified": verified, "integrity_failures": count("Payload Modified"),
        "signature_failures": count("Signature Invalid"), "metadata_failures": count("Metadata Tampered"),
        "duplicates_ignored": duplicates,
        "delivery_percentage": round(100.0 * verified / sent, 2) if sent else 0.0,
        "per_packet": results,
    }
