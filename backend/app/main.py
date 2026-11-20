"""FastAPI application. Run with: uvicorn app.main:app --port 8002"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import graph as G
from . import numtheory as nt
from . import packets as P
from . import recurrence as R
from . import security as S
from . import research as Research
from .state import STATE

API_PORT = 8002
ORIGINS = ["http://localhost:5174", "http://127.0.0.1:5174"]

app = FastAPI(title="IRSD - Interactive Network Routing & Secure Token Dispatcher", version="2.0.0",
              description="Local network-routing research simulator with interactive mixed-class packet transfer and optional authentication experiments. Not a production network emulator or security product.")
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(G.GraphError)
@app.exception_handler(nt.NumberTheoryError)
@app.exception_handler(R.MathInputError)
async def domain_error(_: Request, exc: Any) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": str(exc)}})


# ------------------------------------------------------------------ models
class NodeIn(BaseModel):
    id: str
    x: float | None = None
    y: float | None = None


class EdgeIn(BaseModel):
    u: str
    v: str
    weight: float
    propagation_delay_ms: float | None = Field(default=None, ge=0)
    capacity_mbps: float | None = Field(default=None, gt=0)
    loss_probability: float | None = Field(default=None, ge=0, le=1)
    queue_capacity_packets: int | None = Field(default=None, ge=1, le=100000)
    status: Literal["up", "down"] = "up"


class PositionsIn(BaseModel):
    positions: dict[str, dict[str, float]]


class SampleIn(BaseModel):
    nodes: int = Field(8, ge=2, le=20)
    seed: int | None = None


class TraverseIn(BaseModel):
    source: str
    target: str | None = None


class RouteIn(BaseModel):
    source: str
    target: str


class PacketCreateIn(BaseModel):
    source: str
    destination: str
    route: list[str]
    algorithm: Literal["bfs", "dfs", "dijkstra"]
    payload: str
    count: int = 1


class DispatchIn(BaseModel):
    drop_seqs: list[int] = Field(default_factory=list)
    drop_count: int = 0
    tamper_payload_seqs: list[int] = Field(default_factory=list)
    tamper_route_seqs: list[int] = Field(default_factory=list)
    tamper_token_seqs: list[int] = Field(default_factory=list)
    duplicate_seqs: list[int] = Field(default_factory=list)


class FailureScheduleIn(BaseModel):
    kind: Literal["link", "node"]
    at_ms: float = Field(ge=0)
    duration_ms: float = Field(gt=0)
    u: str | None = None
    v: str | None = None
    node: str | None = None


class PacketProfileIn(BaseModel):
    packet_type: Literal["data", "ack", "control", "voice", "video"]
    size_bytes: int = Field(ge=1, le=65535)
    payload: str = Field(default="", max_length=500)
    scenario: Literal["normal", "drop", "duplicate", "tamper_payload", "tamper_route"] = "normal"


class PacketTransferIn(BaseModel):
    source: str
    destination: str
    algorithm: Literal["bfs", "dijkstra_static", "dijkstra_dynamic"] = "dijkstra_dynamic"
    packet_profiles: list[PacketProfileIn] = Field(min_length=1, max_length=100)
    duration_ms: float = Field(default=3000, ge=10, le=60000)
    traffic_model: Literal["constant", "variable", "burst"] = "constant"
    ttl: int = Field(default=32, ge=1, le=255)
    seed: int = 2026
    failures: list[FailureScheduleIn] = Field(default_factory=list, max_length=10)


class ExperimentIn(BaseModel):
    algorithms: list[Literal["bfs", "dijkstra_static", "dijkstra_dynamic"]] = Field(
        default_factory=lambda: ["dijkstra_static", "dijkstra_dynamic"], min_length=1, max_length=3
    )
    topology: Literal["current", "erdos_renyi", "small_world", "scale_free"] = "current"
    node_count: int = Field(default=12, ge=2, le=100)
    source: str | None = None
    destination: str | None = None
    packet_count: int = Field(default=100, ge=1, le=5000)
    duration_ms: float = Field(default=10000, ge=10, le=3600000)
    packet_size_bytes: int = Field(default=512, ge=1, le=65535)
    traffic_model: Literal["constant", "variable", "burst"] = "constant"
    ttl: int = Field(default=32, ge=1, le=255)
    failures: list[FailureScheduleIn] = Field(default_factory=list, max_length=20)
    security_enabled: bool = False
    tamper_rate: float = Field(default=0.0, ge=0, le=1)
    duplicate_rate: float = Field(default=0.0, ge=0, le=1)
    packet_expiry_ms: float = Field(default=30000, gt=0)
    seed: int = 2026
    repetitions: int = Field(default=3, ge=1, le=30)


class TwoInts(BaseModel):
    a: int
    b: int


class ModInvIn(BaseModel):
    a: int
    m: int


class ModExpIn(BaseModel):
    base: int
    exp: int
    mod: int


class PrimeIn(BaseModel):
    n: int


class KeygenIn(BaseModel):
    bits: int = 24
    e: int = 65537
    p: int | None = None
    q: int | None = None


class CryptIn(BaseModel):
    value: int
    n: int
    key: int  # e for encryption, d for decryption


class TokenCreateIn(BaseModel):
    source: str
    destination: str
    payload: str
    route: list[str] | None = None


class TokenVerifyIn(BaseModel):
    token: dict[str, Any]
    payload: str
    packet_header: dict[str, Any] | None = None


class AdditiveIn(BaseModel):
    initial: float = 100
    increment: float = 25
    steps: int = 10


class BackoffIn(BaseModel):
    initial_delay: float = 100
    factor: float = 2
    steps: int = 8
    cap: float | None = None


class FibIn(BaseModel):
    n: int = 15
    f0: int = 0
    f1: int = 1


class WalksIn(BaseModel):
    degree: int = 3
    steps: int = 6


class PermIn(BaseModel):
    n: int
    k: int


class SimplePathsIn(BaseModel):
    source: str
    target: str


class ExactWalksIn(BaseModel):
    source: str
    target: str
    length: int


# ------------------------------------------------------------------ helpers
def graph_payload() -> dict[str, Any]:
    g = STATE.graph
    return {**g.to_dict(), "version": STATE.version, "weights_simulated": True,
            "note": "Edge weight is routing cost. Propagation delay and other link simulation properties are stored separately; all values are simulator inputs, not measured physical-network values."}


# ------------------------------------------------------------------ health / graph
@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "port": API_PORT, "graph_version": STATE.version}


@app.get("/graph")
def get_graph() -> dict[str, Any]:
    return graph_payload()


@app.get("/graph/export")
def export_graph() -> dict[str, Any]:
    # Export the complete graph model, including simulation properties.
    return {**STATE.graph.to_dict(), "version": STATE.version}


@app.put("/graph")
def import_graph(data: dict[str, Any]) -> dict[str, Any]:
    STATE.replace_graph(G.Graph.from_dict(data))
    return graph_payload()


@app.post("/graph/demo")
def load_demo() -> dict[str, Any]:
    STATE.replace_graph(G.demo_graph())
    return {**graph_payload(), "demo_pair": {"source": G.DEMO_PAIR[0], "target": G.DEMO_PAIR[1]}}


@app.post("/graph/sample")
def load_sample(body: SampleIn) -> dict[str, Any]:
    STATE.replace_graph(G.sample_graph(body.nodes, body.seed))
    return graph_payload()


@app.post("/graph/clear")
def clear_graph() -> dict[str, Any]:
    STATE.replace_graph(G.Graph())
    return graph_payload()


@app.post("/graph/nodes", status_code=201)
def add_node(body: NodeIn) -> dict[str, Any]:
    STATE.graph.add_node(body.id, body.x, body.y)
    STATE.bump()
    return graph_payload()


@app.delete("/graph/nodes/{node_id}")
def delete_node(node_id: str) -> dict[str, Any]:
    STATE.graph.remove_node(node_id)
    STATE.bump()
    return graph_payload()


@app.post("/graph/edges", status_code=201)
def add_edge(body: EdgeIn) -> dict[str, Any]:
    STATE.graph.add_edge(body.u, body.v, body.weight,
                         propagation_delay_ms=body.propagation_delay_ms if body.propagation_delay_ms is not None else 1.0,
                         capacity_mbps=body.capacity_mbps if body.capacity_mbps is not None else 10.0,
                         loss_probability=body.loss_probability if body.loss_probability is not None else 0.0,
                         queue_capacity_packets=body.queue_capacity_packets if body.queue_capacity_packets is not None else 20,
                         status=body.status)
    STATE.bump()
    return graph_payload()


@app.put("/graph/edges")
def update_edge(body: EdgeIn) -> dict[str, Any]:
    properties = {k: v for k, v in {
        "propagation_delay_ms": body.propagation_delay_ms,
        "capacity_mbps": body.capacity_mbps,
        "loss_probability": body.loss_probability,
        "queue_capacity_packets": body.queue_capacity_packets,
        "status": body.status if "status" in body.model_fields_set else None,
    }.items() if v is not None}
    STATE.graph.update_edge(body.u, body.v, body.weight, **properties)
    STATE.bump()
    return graph_payload()


@app.delete("/graph/edges")
def delete_edge(u: str, v: str) -> dict[str, Any]:
    STATE.graph.remove_edge(u, v)
    STATE.bump()
    return graph_payload()


@app.put("/graph/positions")
def set_positions(body: PositionsIn) -> dict[str, Any]:
    for n, pos in body.positions.items():
        if n in STATE.graph.adj:
            STATE.graph.positions[n] = {"x": pos["x"], "y": pos["y"]}
    return {"ok": True}  # layout only: does not change the graph version


@app.get("/graph/analysis")
def analysis() -> dict[str, Any]:
    return {**STATE.graph.analysis(), "operational": STATE.graph.operational_analysis(), "version": STATE.version}


@app.get("/graph/components")
def components() -> dict[str, Any]:
    return {"components": STATE.graph.components(), "connected": STATE.graph.is_connected()}


@app.get("/graph/euler")
def euler() -> dict[str, Any]:
    return STATE.graph.euler()


@app.get("/graph/hamiltonian")
def hamiltonian(kind: Literal["path", "cycle"] = "path") -> dict[str, Any]:
    return STATE.graph.hamiltonian(kind == "cycle")


@app.get("/graph/coloring")
def coloring() -> dict[str, Any]:
    return STATE.graph.greedy_coloring()


@app.post("/graph/traverse/{algo}")
def traverse(algo: Literal["bfs", "dfs"], body: TraverseIn) -> dict[str, Any]:
    fn = G.bfs_trace if algo == "bfs" else G.dfs_trace
    return {**fn(STATE.graph, body.source, body.target), "graph_version": STATE.version}


# ------------------------------------------------------------------ routing
@app.post("/routing/{algo}")
def route(algo: str, body: RouteIn) -> dict[str, Any]:
    return {**G.compute_route(STATE.graph, algo, body.source, body.target), "graph_version": STATE.version}


# ------------------------------------------------------------------ packets
@app.post("/packets/create", status_code=201)
def create_packets(body: PacketCreateIn) -> dict[str, Any]:
    STATE.batch = P.create_batch(STATE.graph, STATE.registry, STATE.version, body.source, body.destination,
                                 body.route, body.algorithm, body.payload, body.count)
    STATE.last_dispatch = None
    return STATE.batch


@app.post("/packets/dispatch")
def dispatch_packets(body: DispatchIn) -> dict[str, Any]:
    if STATE.batch is None:
        raise G.GraphError("Create a packet batch before dispatching.", "no_batch", 409)
    if STATE.batch["graph_version"] != STATE.version:
        raise G.GraphError("The graph changed after this batch was created; recompute the route and recreate packets.", "stale_route", 409)
    STATE.last_dispatch = P.dispatch(STATE.graph, STATE.registry, STATE.batch, body.model_dump())
    return STATE.last_dispatch


@app.get("/packets/report")
def packet_report() -> dict[str, Any]:
    if STATE.last_dispatch is None:
        raise G.GraphError("No dispatch has been run yet.", "no_dispatch", 404)
    return STATE.last_dispatch["report"]


@app.post("/packets/reset")
def reset_packets() -> dict[str, Any]:
    STATE.batch = None
    STATE.last_dispatch = None
    return {"ok": True}


@app.post("/packets/transfer")
def simulate_packet_transfer(body: PacketTransferIn) -> dict[str, Any]:
    """Run a visible multi-class packet transfer on the current network graph.

    Unlike the legacy token demo, this endpoint models packet sizes, FIFO link
    queues, serialization, propagation, link loss, TTL and optional failures.
    Packet classes are simulated traffic profiles rather than protocol claims.
    """
    graph = STATE.graph
    try:
        graph.require(body.source)
        graph.require(body.destination)
        if body.source == body.destination:
            raise ValueError("Source and destination must be different.")
        profiles = [profile.model_dump() for profile in body.packet_profiles]
        config: dict[str, Any] = {
            "source": body.source,
            "destination": body.destination,
            "packet_count": len(profiles),
            "packet_size_bytes": max(profile["size_bytes"] for profile in profiles),
            "duration_ms": body.duration_ms,
            "traffic_model": body.traffic_model,
            "ttl": body.ttl,
            "security_enabled": False,
            "tamper_rate": 0.0,
            "duplicate_rate": 0.0,
            "packet_expiry_ms": body.duration_ms * 2,
            "packet_profiles": profiles,
            "include_trace": True,
            "failures": [failure.model_dump(exclude_none=True) for failure in body.failures],
        }
        result = Research.simulate(graph_payload(), config, algorithm=body.algorithm,
                                   seed=body.seed, repetition=1)
        return {
            "transfer_id": uuid.uuid4().hex[:10].upper(),
            "graph_version": STATE.version,
            "source": body.source,
            "destination": body.destination,
            "algorithm": body.algorithm,
            "traffic_model": body.traffic_model,
            "packet_count": len(profiles),
            "metrics": result["metrics"],
            "packets": result["packet_outcomes"],
            "trace_events": result.get("trace_events", []),
            "trace_truncated": result.get("trace_truncated", False),
            "note": "Local discrete-event simulation. Packet classes are illustrative traffic profiles; no real network packets are transmitted.",
        }
    except (ValueError, G.GraphError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/experiments/run")
def run_experiment(body: ExperimentIn) -> dict[str, Any]:
    config = body.model_dump(exclude={"algorithms", "repetitions", "topology", "node_count", "seed"})
    config["seed"] = body.seed
    try:
        topology = STATE.graph if body.topology == "current" else Research.generate_topology(body.topology, body.node_count, body.seed)
        if len(topology.nodes) < 2:
            raise ValueError("Load or generate a topology with at least two nodes before running experiments.")
        source = body.source or topology.nodes[0]
        destination = body.destination or topology.nodes[-1]
        topology.require(source)
        topology.require(destination)
        if source == destination:
            raise ValueError("Source and destination must be different.")
        config["source"], config["destination"] = source, destination
        config["failures"] = [f.model_dump(exclude_none=True) for f in body.failures]
        for failure in config["failures"]:
            if failure["kind"] == "link" and not (failure.get("u") and failure.get("v")):
                raise ValueError("Link failure requires u and v node IDs.")
            if failure["kind"] == "node" and not failure.get("node"):
                raise ValueError("Node failure requires a node ID.")
        return Research.run_suite(topology, config, body.algorithms, body.repetitions)
    except (ValueError, G.GraphError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/experiments")
def experiments(limit: int = 50) -> dict[str, Any]:
    return {"experiments": Research.list_experiments(max(1, min(limit, 100)))}


@app.get("/experiments/runs/{run_id}/packets")
def experiment_packet_outcomes(run_id: str, offset: int = 0, limit: int = 100) -> dict[str, Any]:
    try:
        return Research.get_packet_outcomes(run_id, offset=offset, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Experiment run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/experiments/{comparison_id}")
def experiment_detail(comparison_id: str) -> dict[str, Any]:
    try:
        return Research.get_experiment(comparison_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Experiment not found.") from exc


# ------------------------------------------------------------------ number theory & toy RSA
@app.post("/numtheory/gcd")
def api_gcd(b: TwoInts) -> dict[str, Any]:
    return {"gcd": nt.gcd(b.a, b.b), "steps": nt.gcd_steps(b.a, b.b)}


@app.post("/numtheory/egcd")
def api_egcd(b: TwoInts) -> dict[str, Any]:
    g, x, y = nt.ext_gcd(b.a, b.b)
    return {"gcd": g, "x": x, "y": y, "identity": f"{b.a}*({x}) + {b.b}*({y}) = {g}",
            "verified": b.a * x + b.b * y == g, "table": nt.ext_gcd_steps(b.a, b.b)}


@app.post("/numtheory/modinv")
def api_modinv(b: ModInvIn) -> dict[str, Any]:
    inv = nt.mod_inverse(b.a, b.m)
    return {"inverse": inv, "check": f"{b.a} * {inv} mod {b.m} = {(b.a * inv) % b.m}"}


@app.post("/numtheory/modexp")
def api_modexp(b: ModExpIn) -> dict[str, Any]:
    return {"result": nt.mod_exp(b.base, b.exp, b.mod)}


@app.post("/numtheory/prime-test")
def api_prime(b: PrimeIn) -> dict[str, Any]:
    return {"n": b.n, "probably_prime": nt.is_probable_prime(b.n)}


@app.post("/rsa/keys")
def api_keys(b: KeygenIn) -> dict[str, Any]:
    kp = nt.keypair_from_primes(b.p, b.q, b.e) if b.p and b.q else nt.generate_keypair(b.bits, b.e)
    return {"p": kp.p, "q": kp.q, "n": kp.n, "phi": kp.phi, "public": kp.public(), "private": kp.private(),
            "steps": kp.steps(), "warning": nt.TOY_WARNING}


@app.post("/rsa/encrypt")
def api_encrypt(b: CryptIn) -> dict[str, Any]:
    return {"ciphertext": nt.encrypt_int(b.value, b.n, b.key), "warning": nt.TOY_WARNING}


@app.post("/rsa/decrypt")
def api_decrypt(b: CryptIn) -> dict[str, Any]:
    return {"plaintext": nt.decrypt_int(b.value, b.n, b.key), "warning": nt.TOY_WARNING}


@app.post("/tokens/create", status_code=201)
def api_token_create(b: TokenCreateIn) -> dict[str, Any]:
    g = STATE.graph
    g.require(b.source)
    g.require(b.destination)
    route_ = b.route or (G.dijkstra_trace(g, b.source, b.destination)["path"])
    if not route_:
        raise G.GraphError("No route exists between source and destination.", "no_route", 409)
    P.validate_route(g, b.source, b.destination, route_)
    tok = S.create_token(STATE.registry, f"MANUAL-{b.source[:3].upper()}-{b.destination[:3].upper()}", 1,
                         b.source, b.destination, route_, b.payload)
    return {"token": tok, "payload": b.payload, "warning": nt.TOY_WARNING}


@app.post("/tokens/verify")
def api_token_verify(b: TokenVerifyIn) -> dict[str, Any]:
    required = {"packet_id", "seq", "source", "destination", "route", "payload_digest", "encrypted_nonce", "signature"}
    missing = required - set(b.token)
    if missing:
        raise G.GraphError(f"Token is missing fields: {sorted(missing)}.", "invalid_token")
    for node in (b.token["source"], b.token["destination"]):
        if node not in STATE.registry.keys:
            raise G.GraphError(f"No keys registered for '{node}'; create a token first.", "unknown_keys", 404)
    return {**S.verify_token(STATE.registry, b.token, b.payload, b.packet_header), "warning": nt.TOY_WARNING}


# ------------------------------------------------------------------ Unit 4 math lab
@app.post("/math/additive")
def m_additive(b: AdditiveIn) -> dict[str, Any]:
    return R.additive_growth(b.initial, b.increment, b.steps)


@app.post("/math/backoff")
def m_backoff(b: BackoffIn) -> dict[str, Any]:
    return R.exponential_backoff(b.initial_delay, b.factor, b.steps, b.cap)


@app.post("/math/fibonacci")
def m_fib(b: FibIn) -> dict[str, Any]:
    return R.fibonacci(b.n, b.f0, b.f1)


@app.post("/math/walks")
def m_walks(b: WalksIn) -> dict[str, Any]:
    return R.walk_count_regular(b.degree, b.steps)


@app.post("/math/walks-exact")
def m_walks_exact(b: ExactWalksIn) -> dict[str, Any]:
    n = STATE.graph.count_walks_exact(b.source, b.target, b.length)
    return {"walks": str(n), "source": b.source, "target": b.target, "length": b.length,
            "note": "Exact count from the current graph (entry of A^n). Compare with d^n, valid only for regular branching."}


@app.post("/math/permutations")
def m_perm(b: PermIn) -> dict[str, Any]:
    return R.k_permutations(b.n, b.k)


@app.post("/math/simple-paths")
def m_simple(b: SimplePathsIn) -> dict[str, Any]:
    return {"count": STATE.graph.count_simple_paths(b.source, b.target), "source": b.source, "target": b.target,
            "guard": f"At most {G.MAX_PATH_COUNT_NODES} nodes."}


@app.get("/math/concepts")
def m_concepts() -> list[dict[str, str]]:
    return R.CONCEPTS
