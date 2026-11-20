# Software Requirements Specification Addendum — Research Edition

## Purpose

This addendum updates the original project organization. The primary application is now organized around Network Studio, Routing & Resilience, Packet Transfer, Experiments, Results & Analytics and Methodology rather than academic unit navigation.

## Functional requirements

- Edit an undirected graph with routing cost and independent link simulation properties.
- Visualize BFS/DFS/Dijkstra traces.
- Simulate BFS minimum-hop, frozen Static Dijkstra and adaptive Dynamic Dijkstra routing.
- Create mixed packet batches from a user-entered payload template using DATA, ACK, CONTROL, VOICE and VIDEO traffic profiles with individual payload sizes.
- Simulate hop-by-hop packet transfer with event playback, per-packet fault injection, FIFO queues, serialization, propagation delay, capacity, loss probability, TTL and scheduled node/link failures.
- Retain Ed25519/SHA-256 as an optional authentication variable in research experiments, rather than a separate static Packet Security page.
- Execute repeated matched-seed algorithm comparisons.
- Persist topology snapshots, configurations, seeds, metrics and run outcomes in SQLite.
- Display aggregate metrics and paired differences; export result data.

## Non-functional requirements

- API and frontend run locally on ports 8002 and 5174.
- Input validation and meaningful HTTP errors.
- Deterministic logical simulation for fixed snapshots/configuration/seeds.
- Explicit reporting of runtime-dependent cryptographic timings.
- Clear limitations for the simplified network model and security scope.

## Constraints

- Undirected graphs only.
- Static Dijkstra uses destination-specific time-zero forwarding entries.
- Dynamic Dijkstra recalculates after simulated topology version changes.
- BFS ignores weighted routing cost.
- No packet confidentiality is claimed.
- Experiments execute synchronously within configured safety limits.
