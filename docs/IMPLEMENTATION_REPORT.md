# IRSD Research Edition — Implementation Report

## Delivery scope

This release transforms the original IRSD application into a research-oriented local network-routing and packet-transfer simulator with optional packet-authentication experiments. The original source ZIP is not modified; this report describes a separate working copy derived from it.

## Implemented changes

### Application structure

- Replaced the academic-unit primary navigation with Dashboard, Network Studio, Routing & Resilience, Packet Transfer, Experiments, Results & Analytics, and Methodology.
- Made Dashboard a separate overview page rather than a duplicate of the graph workspace.
- Added a dedicated routing/resilience explainer and replaced the static Packet Security page with an interactive Packet Transfer module.
- Removed Unit 4/5/6 labels from primary navigation. Legacy math/number-theory endpoints and source modules are retained for compatibility, not as the principal research workflow.

### Graph model and network studio

- Preserved `weight` as routing cost and `propagation_delay_ms` as an independent link delay.
- Added/retained link capacity, loss probability, FIFO queue capacity and status as separate properties.
- Preserved supported operational properties through graph import/export.
- Added operational graph analysis that excludes failed nodes/links from active connectivity statistics.
- Added queue-capacity controls to link creation/editing.
- Kept the existing graph workspace's BFS/DFS/Dijkstra traces and editing functionality.

### Research simulator

- Added a local discrete-event packet simulator with per-direction FIFO queues, full-duplex link abstraction, serialization and propagation delay, packet loss, queue overflow, TTL, timed node/link failures and differentiated packet terminal states.
- Implemented BFS as an unweighted minimum-hop baseline.
- Implemented static Dijkstra with destination-specific per-router forwarding entries frozen at simulation time zero.
- Implemented dynamic Dijkstra with route recalculation after supported topology changes.
- Added deterministic seeded Erdős–Rényi-connected, small-world and scale-free topology generators.
- Added constant, variable/Poisson-like and burst traffic generation.
- Added matched-seed experiment comparisons and per-run configuration/topology provenance.

### Security

- Retained Ed25519 packet signing and verification with SHA-256 payload digest binding as an optional experiment capability; it is no longer presented as a standalone static user module.
- The signed canonical envelope includes packet identifiers, source/destination, payload digest, timestamps/expiry and nonce.
- Added tamper, expiry and replay checks in the optional research authentication experiment path.
- Explicitly distinguish authentication/integrity from confidentiality: packets are not encrypted.
- Kept private keys ephemeral; no production key-management claim is made.

### Interactive Packet Transfer

- Replaced the static Packet Security navigation page with a live packet batch creation and hop-by-hop transfer simulation.
- Added a custom payload template plus DATA, ACK, CONTROL, VOICE and VIDEO traffic profiles with individually configurable byte sizes. These classes are illustrative simulator profiles, not exact wire-protocol definitions.
- Added per-packet scenarios: normal delivery, simulated packet loss on a selected route edge, payload modification, route-metadata alteration and duplicate arrival.
- Corrected packet-loss semantics to match the original IRSD dispatcher: a packet selected for loss is not skipped at the source or discarded before a link. It travels through preceding hops, queues on the loss edge, is serialized and incurs propagation delay, then is recorded as lost before reaching the next node.
- Added trace events with the exact loss-edge endpoints, per-packet edge-attempt history and `lost_on_edge` outcome data. Packet Transfer replay highlights the actual loss edge in dark red, shows the packet ID on that edge, and removes the marker when replay is stepped back before the loss event.
- Added packet transmission metrics for hop attempts and bytes serialized, including packets that are subsequently lost.
- Reused the discrete-event engine for FIFO queueing, serialization, propagation delay, capacity, loss, TTL, timed failures and routing-policy behaviour.
- Added playback controls, packet-class-colored markers, a bounded event trace, per-packet route history and a JSON transmission export.
- Removed the standalone static Packet Security page. Ed25519/SHA-256 remains optional in experiment configuration for authentication-overhead studies.

### Experiments, statistics and result storage

- Added SQLite-backed experiment groups and run records with topology snapshots, config, seed, repetition, application/runtime provenance and summary metrics.
- Separated packet-level outcomes into an indexed SQLite table instead of including all per-packet records in normal comparison responses.
- Added a bounded paginated endpoint: `GET /experiments/runs/{run_id}/packets?offset=0&limit=100`.
- Added UI inspection and pagination for packet-level outcomes in Results & Analytics.
- Added numerical Student-t critical-value inversion for 95% confidence intervals.
- Paired comparisons match by repetition and seed and report candidate-minus-reference differences.
- Added metrics for packet delivery/loss, throughput, latency, route recovery, recalculations, queue overflow and security timing/results.

### Local configuration

- Frontend: `http://127.0.0.1:5174`
- Backend: `http://127.0.0.1:8002`
- API URL: `http://127.0.0.1:8002`
- CORS allows `http://localhost:5174` and `http://127.0.0.1:5174`.

## Verification

- Backend test suite: **67 passed**.
- Python source/test compilation: passed.
- Frontend TypeScript/TSX syntax parse: **21 files, 0 syntax diagnostics**.
- Static relative import check: **45 relative paths and 105 local imported names checked; 0 unresolved paths or missing exports**.
- Frontend dependency installation: not completed in the packaging environment; `npm ci` timed out on repeated attempts.
- Therefore frontend Vitest, full TypeScript semantic type-check and Vite production build are **not verified** in this delivery.
- Backend TestClient integration covers health/port, interactive packet transfer, mixed packet classes and per-packet fault scenarios, experiment creation/persistence/detail, paginated packet outcomes, invalid failure schedules and operational graph analysis.
- No full browser-driven end-to-end session was run in this packaging environment.

## Important limitations

- This is an educational/research discrete-event model, not a physical network emulator or validated simulator such as ns-3/OMNeT++.
- The graph model is undirected.
- The active graph is held in backend process memory and resets on restart unless exported.
- Static Dijkstra is scoped to one selected destination per experiment, with a time-zero forwarding entry per router; it does not model all destinations concurrently.
- Generated topologies are connected by construction; the Erdős–Rényi model adds a spanning tree and therefore is not an unconstrained G(n,p) sample.
- The current UI exposes scheduled failure selection for the current Network Studio graph. Generated-topology failure selection is available through API-level configuration but not yet exposed with a generated-edge picker in the UI.
- Experiments execute synchronously with a 60,000-packet comparison budget and one-million-event per-run limit. Background jobs, progress polling and cancellation are not implemented.
- TCP, retransmissions, processing delay, routing-control overhead, CPU/memory telemetry and physical network effects are not modelled.
- Signing/verification timings are wall-clock measurements and are environment-dependent.
- Ed25519/SHA-256 provide authenticity/integrity, not confidentiality. Key persistence, rotation, revocation and trust distribution are not implemented.
- Confidence intervals quantify variation across repeated simulation runs, not uncertainty in the model assumptions or external validity.

## Recommended first verification on the receiving Mac

After extracting this release into a new folder:

```bash
# Terminal 1
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

```bash
# Terminal 2
cd frontend
npm install
npm test
npm run build
npm run dev
```

Open `http://127.0.0.1:5174` and verify the API at `http://127.0.0.1:8002/docs`.

Run the full frontend test and build on the Mac before relying on the interface for a formal presentation, because those two checks could not be completed in the packaging environment.
