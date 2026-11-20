# IRSD — Interactive Network Routing & Secure Token Dispatcher

IRSD is a local research-oriented network-routing and packet-transfer simulator. It brings together graph-based topology editing, routing and resilience experiments, mixed-class packet creation and hop-by-hop transfer simulation, optional Ed25519/SHA-256 authentication experiments, and persisted results.

> **Scope:** IRSD is an educational/research simulator. It is not a production network emulator, router, security appliance, or cryptographic service. Its results are simulated measurements, not measurements from physical network equipment. The Packet Transfer module simulates packet classes and network events; it does not send real network traffic. Optional Ed25519/SHA-256 authentication experiments provide authenticity/integrity, not encryption.

## Research focus

The primary empirical comparison is:

- **BFS:** minimum-hop baseline on an unweighted interpretation of the graph. It ignores routing-cost weights.
- **Static Dijkstra:** a time-zero forwarding entry is frozen for each router for the selected destination; a failure does not trigger recomputation.
- **Dynamic Dijkstra:** routes are recalculated from a packet's current router when a scheduled failure or recovery changes topology.

ARAR is not part of the primary comparison. The older classroom RSA/number-theory and recurrence demonstrations remain in the backend for backward compatibility but are not presented as the primary security or research workflow in the new navigation.

Routing cost and propagation delay are intentionally separate:

- `weight` is the routing cost optimized by Dijkstra.
- `propagation_delay_ms` is the delay added after serialization on a link.

The simulator also models link capacity, packet loss probability, FIFO queue capacity, TTL, and temporary link/node failures. In Packet Transfer, a packet configured for simulated loss is still dispatched: it traverses earlier hops, is queued and serialized on its selected loss edge, incurs propagation delay, and is then recorded as lost before reaching the next node. The replay highlights that exact edge in dark red and identifies the packet ID.

## Application modules

| Module | Purpose |
|---|---|
| Dashboard | Backend health, current topology overview, saved experiment groups |
| Network Studio | Interactive graph editing, link configuration, import/export |
| Routing & Resilience | Interactive BFS/DFS/Dijkstra route trace plus links to resilience experiments |
| Packet Transfer | Create mixed packet batches, assign per-packet scenarios, animate hop-by-hop delivery, inspect outcomes and export traces |
| Experiments | Matched-seed comparisons across algorithms, topology families, traffic patterns and scheduled failures |
| Results & Analytics | Persisted per-run observations, summaries, confidence intervals, paired differences and exports |
| Methodology | Simulation assumptions, metric definitions and limitations |

## Requirements

- Python 3.10 or newer (Python 3.13/3.14 is suitable).
- Node.js 24.x recommended for the locked frontend toolchain.
- npm.

## Local ports

The project is configured for these local endpoints. Do not change them back to the original defaults:

- Frontend: <http://127.0.0.1:5174>
- Backend: <http://127.0.0.1:8002>
- FastAPI docs: <http://127.0.0.1:8002/docs>

The frontend API URL is `http://127.0.0.1:8002`. Backend CORS allows both `http://localhost:5174` and `http://127.0.0.1:5174`.

## Setup on macOS

Open two terminal windows from the extracted project directory.

### Terminal 1 — backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

### Terminal 2 — frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5174>.

The frontend `.env` file is configured as:

```env
VITE_API_URL=http://127.0.0.1:8002
```

If `.env` is missing, copy `.env.example` to `.env` and keep the same value. Restart Vite after changing environment variables.

## Tests and build

Backend tests:

```bash
cd backend
python -m pytest -q
```

Frontend tests and production build (after `npm install`):

```bash
cd frontend
npm test
npm run build
```

## Experiments and persistence

Experiment comparisons are stored in `backend/data/irsd_research.sqlite3`, created on first use. Each run records the topology snapshot, configuration, random seed, repetition, summary metrics, timestamp, application version, and runtime/dependency provenance. Packet-level outcomes are stored separately and can be fetched in bounded pages through the API. This database is local to the extracted project directory.

The synchronous experiment endpoint applies safety limits: up to 30 repetitions, up to 5,000 packets per run, a maximum of 60,000 packets across all selected algorithms and repetitions, and a one-million-event cap per simulation run. Large experiment execution can block the API request; asynchronous job execution is not implemented in this delivery.

## Project structure

```text
interactive-network-routing-secure-token-dispatcher/
├── backend/
│   ├── app/
│   │   ├── graph.py              # graph model and graph algorithms
│   │   ├── main.py               # FastAPI routes and request models
│   │   ├── research.py           # event simulation, experiments, statistics, SQLite
│   │   ├── packet_security.py    # optional Ed25519 + SHA-256 experiment mechanism
│   │   ├── packets.py            # legacy classroom packet/token demo
│   │   ├── numtheory.py          # legacy mathematical demonstrations
│   │   └── recurrence.py         # legacy recurrence demonstrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/           # research modules, PacketTransfer and reusable UI
│       ├── App.tsx               # research-oriented navigation
│       ├── api.ts                # typed API client
│       └── types.ts              # graph, transfer and research API type models
└── docs/                         # architecture, methodology and limitations
```

## Documentation

See `docs/` for the system architecture, API reference, algorithm definitions, Packet Transfer guide, simulation model, optional security experiment model, experimental methodology, metric definitions, test report, known limitations, and a research-paper outline.

## Important interpretation note

A reproducible simulation is not automatically evidence of real-world network performance. Report the model assumptions, use matched experiment configurations, run enough independent repetitions for the question being studied, and interpret wall-clock cryptographic timings as machine/runtime-dependent. Do not present this simulator as a novel routing algorithm or as proof of a production security guarantee.
