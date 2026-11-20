# API Documentation

Base URL: `http://127.0.0.1:8002`

FastAPI's interactive schema is available at `/docs`.

## Health and graph

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Backend health and configured API port |
| GET | `/graph` | Current graph, simulation properties and version |
| GET | `/graph/export` | Export full graph attributes |
| PUT | `/graph` | Validate/import graph JSON |
| POST | `/graph/demo` | Load demo topology |
| POST | `/graph/sample` | Generate a small sample graph |
| POST | `/graph/clear` | Clear active graph |
| POST | `/graph/nodes` | Add node |
| DELETE | `/graph/nodes/{node_id}` | Delete node |
| POST | `/graph/edges` | Add edge and link properties |
| PUT | `/graph/edges` | Update routing cost and/or link properties |
| DELETE | `/graph/edges?u=...&v=...` | Delete edge |
| PUT | `/graph/positions` | Update visual node positions |
| GET | `/graph/analysis` | Structural analysis plus `operational` status analysis |
| GET | `/graph/components` | Structural connected components |
| POST | `/graph/traverse/{bfs\|dfs}` | BFS/DFS traversal |
| POST | `/routing/{bfs\|dfs\|dijkstra}` | Single route with execution trace |

For edge creation/update, the request may include:

```json
{
  "u": "Main Gate",
  "v": "Library",
  "weight": 4.0,
  "propagation_delay_ms": 12.0,
  "capacity_mbps": 10.0,
  "loss_probability": 0.01,
  "queue_capacity_packets": 20,
  "status": "up"
}
```

`weight` is routing cost. `propagation_delay_ms`, `capacity_mbps`, `loss_probability`, `queue_capacity_packets` and `status` are independent link properties.

## Interactive Packet Transfer

### POST `/packets/transfer`

Run a one-off mixed-traffic transfer on the currently active graph and return a bounded, ordered event trace plus individual packet outcomes.

Example request:

```json
{
  "source": "Main Gate",
  "destination": "Data Center",
  "algorithm": "dijkstra_dynamic",
  "packet_profiles": [
    {"packet_type": "data", "size_bytes": 512, "payload": "application message", "scenario": "normal"},
    {"packet_type": "ack", "size_bytes": 64, "payload": "ack", "scenario": "duplicate"},
    {"packet_type": "video", "size_bytes": 1400, "payload": "frame", "scenario": "drop"}
  ],
  "duration_ms": 2500,
  "traffic_model": "constant",
  "ttl": 24,
  "seed": 2026,
  "failures": []
}
```

- `algorithm`: `bfs`, `dijkstra_static` or `dijkstra_dynamic`.
- `packet_type`: `data`, `ack`, `control`, `voice` or `video`. These are illustrative traffic profiles, not exact protocol-wire formats.
- `size_bytes`: individual packet payload size, 1–65,535 bytes; serialization delay uses this size.
- `scenario`: `normal`, `drop`, `duplicate`, `tamper_payload` or `tamper_route`.
- `traffic_model`: `constant`, `variable` or `burst`.
- `failures`: optional timed link/node failure schedule, within the configured traffic window.

The response includes `metrics`, `packets`, `trace_events`, and `trace_truncated`. A per-packet `drop` scenario is not discarded before dispatch: it travels earlier route hops, queues and serializes on the selected middle route edge, incurs that edge's propagation delay, and is then lost before the next node. The trace emits `transmitting`, `serialization_complete` and `packet_lost_on_link` with the exact `from_node`/`to_node` pair. Each outcome includes `attempted_hops`, `edge_attempts` and `lost_on_edge`; the UI highlights that exact edge dark red and labels it with the packet ID. Seeded edge `loss_probability` outcomes follow the same in-flight sequence. Other packet statuses distinguish normal delivery, payload/route-metadata modification, link/node failure, queue overflow, no route and TTL expiry. Duplicate copies are counted separately from unique packet delivery. The endpoint runs a local simulation only; it does not send real network packets. Invalid graphs, nodes or profile values return HTTP 422.

## Optional packet-authentication experiments

The standalone `/security/demo` interface has been removed. Ed25519/SHA-256 can still be enabled as an optional variable in `POST /experiments/run` to measure authentication overhead. It demonstrates authenticity/integrity only; packet payloads are not encrypted.

## Research experiments

### POST `/experiments/run`

Key request fields:

- `algorithms`: one or more of `bfs`, `dijkstra_static`, `dijkstra_dynamic`.
- `topology`: `current`, `erdos_renyi`, `small_world`, or `scale_free`.
- `node_count`: generated topology node count (2–100).
- `source`, `destination`: selected traffic pair.
- `packet_count`: 1–5,000 packets per run.
- `duration_ms`: 10–3,600,000 ms traffic-generation window.
- `packet_size_bytes`: 1–65,535.
- `traffic_model`: `constant`, `variable`, or `burst`.
- `ttl`: 1–255 hops.
- `failures`: timed link/node failure schedule.
- `security_enabled`: enable Ed25519 authentication.
- `tamper_rate`, `duplicate_rate`: probabilities in [0,1]. Duplicate injection is a replay test and only applies when security is enabled.
- `packet_expiry_ms`: signed packet expiry interval.
- `seed`: base random seed.
- `repetitions`: 1–30.

Example:

```json
{
  "algorithms": ["dijkstra_static", "dijkstra_dynamic"],
  "topology": "current",
  "source": "Main Gate",
  "destination": "Data Center",
  "packet_count": 100,
  "duration_ms": 10000,
  "packet_size_bytes": 512,
  "traffic_model": "constant",
  "ttl": 32,
  "failures": [
    {"kind":"link","u":"Main Gate","v":"Library","at_ms":2500,"duration_ms":2500}
  ],
  "security_enabled": true,
  "tamper_rate": 0.0,
  "duplicate_rate": 0.0,
  "packet_expiry_ms": 30000,
  "seed": 2026,
  "repetitions": 3
}
```

The API uses the current graph if `topology` is `current`, or generates a topology for the other families. It validates source/destination and failure references. Validation failures return HTTP 422.

The local synchronous runner limits total simulated packets to 60,000 per comparison and processes no more than one million events per individual run. The run response contains outcome counts, not the full packet-outcome arrays.

### GET `/experiments`

Returns recent saved comparison groups. Optional `limit` is clamped to 1–100.

### GET `/experiments/{comparison_id}`

Returns run observations, the persisted topology/configuration, reconstructed metric summaries, matched paired differences and runtime provenance. Packet-level outcomes are counted but omitted from this summary response.

### GET `/experiments/runs/{run_id}/packets?offset=0&limit=100`

Returns a bounded page of packet-level terminal outcomes for one run. `limit` must be between 1 and 500. The outcome records are stored separately from run summary metrics to keep comparison responses small.

## Errors

- Graph domain errors use the project's structured error response and appropriate HTTP status.
- Pydantic input validation errors return 422.
- Unknown experiment IDs return 404.
- Experiment budget or configuration errors return 422.

## Persistence

SQLite is created at `backend/data/irsd_research.sqlite3` on first use. It stores experiment run records and detailed packet outcomes. The active graph itself is currently in-memory and should be exported if it must be retained across backend restarts.
