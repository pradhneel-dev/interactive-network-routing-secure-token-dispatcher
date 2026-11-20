# IRSD Architecture

## Overview

IRSD is a local React/TypeScript frontend backed by a Python/FastAPI service. The frontend edits a graph and submits typed API requests. The backend owns the authoritative in-memory graph, computes graph analyses and route traces, runs discrete-event simulations and packet-transfer traces, optionally performs packet authentication experiments, and persists research experiments in SQLite.

## Main components

### Frontend

- `App.tsx`: research-oriented navigation and application shell.
- `ResearchDashboard.tsx`: API health, graph overview and recent saved comparisons.
- `Workspace.tsx`: Network Studio graph editing and interactive BFS/DFS/Dijkstra route trace.
- `PacketTransfer.tsx`: packet batch creation, mixed traffic profiles, per-packet fault scenarios, discrete-event transfer playback and transmission report.
- `RoutingResilience.tsx`: explains the routing baselines and links to the experiment runner.
- `ResearchLab.tsx`: experiment configuration and matched comparisons.
- `ResearchResults.tsx`: persisted run observations, summary statistics, paired differences and CSV/JSON export.
- `Methodology.tsx`: current simulation assumptions and interpretation notes.
- `api.ts`: typed fetch wrapper and API response types.

The old unit-organized Number Theory and Math Lab components are no longer in primary navigation. Their backend endpoints are retained to avoid deleting useful legacy demonstrations.

### Backend

- `graph.py`: undirected weighted graph, node/link properties, graph operations, traversals, routing and structural/operational analysis.
- `main.py`: FastAPI request models, CORS, graph routes, `/packets/transfer` and experiment endpoints.
- `research.py`: topology generation, path calculation, event scheduling, packet/link simulation, metrics, statistics and SQLite persistence.
- `packet_security.py`: canonical packet envelope, SHA-256 digest and Ed25519 signature/verification.
- `packets.py`, `security.py`, `numtheory.py`, `recurrence.py`: retained legacy academic/demo functionality.

## Data flow

1. The frontend requests the current graph from `/graph` and graph statistics from `/graph/analysis`.
2. Graph edits are sent to the backend. The backend validates changes and updates its in-memory graph state.
3. Packet Transfer sends packet profiles, routing choices and optional timed failures to `/packets/transfer`; the endpoint returns a bounded event trace and per-packet outcomes. Experiment requests contain algorithm choices, topology, traffic/failure/optional security settings, repetition count and base seed.
4. The backend snapshots the selected topology once, then executes each algorithm under matched seed/configuration pairs.
5. Each run's configuration, topology snapshot and summary metrics are persisted in the run table; packet-level outcomes are stored in a separate indexed table and returned through a paginated endpoint.
6. Summary statistics and paired differences are returned to the frontend. Historical summaries are reconstructed from persisted per-run data.

## State and persistence

- The active editable graph is held in the backend process memory (`STATE`). It resets when the backend process restarts unless exported/imported.
- Experiment results persist in `backend/data/irsd_research.sqlite3`.
- Cryptographic identity keys are ephemeral for an optional authentication-enabled experiment run. They are not persisted or rotated as a production key-management system.
- The replay cache is scoped to a simulation run.

## Local endpoints

- Frontend: `http://127.0.0.1:5174`
- Backend: `http://127.0.0.1:8002`
- API docs: `http://127.0.0.1:8002/docs`

## Design boundaries

- `weight` is routing cost. It is not propagation delay.
- `propagation_delay_ms` contributes separately to simulated packet delay.
- BFS is a minimum-hop algorithm for an unweighted interpretation of the topology.
- DFS is available in the interactive graph workspace as a traversal demonstration. It is not a shortest-path method and is not a primary network experiment baseline.
- Static/Dynamic Dijkstra in research experiments have different routing update policies.
- Authentication and integrity are not confidentiality; payloads are not encrypted.
