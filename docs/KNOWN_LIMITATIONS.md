# Known Limitations

This document describes limitations of the delivered implementation. A feature not listed as implemented should not be assumed to exist.

## Network and graph model

- Graphs are undirected. Directed routing topologies are not supported.
- The active graph is in backend process memory and resets on backend restart unless exported.
- Static Dijkstra freezes a destination-specific forwarding entry per router for one selected source/destination experiment; it does not simulate all possible destinations concurrently.
- BFS ignores edge weights and is meaningful as a minimum-hop baseline on an unweighted interpretation only.
- DFS remains an educational traversal demonstration and is not a shortest-path method.

## Simulation

- The simulator is event-driven but simplified; it is not NS-3, OMNeT++, a real network stack or a physical network emulator.
- TCP, retransmissions, routing control messages, processing delay, CPU/memory utilization and wireless effects are not modelled.
- Link queues are per direction and use a full-duplex abstraction.
- A transmission interrupted during serialization is invalidated; propagation already in flight is allowed to complete.
- The route-recovery metric measures the first successful packet arrival after a packet has adapted its route following the first failure; it is not a control-plane convergence timer.
- Link loss decisions are deterministic for a fixed seed/packet/link/hop so paired experiments can be reproduced; they are not a time-correlated physical channel model.
- Experiments run synchronously. A packet/event safety cap prevents unbounded workloads, but a large valid experiment can still occupy the API process while running. Background jobs, progress polling and cancellation are not yet implemented.
- The local experiment budget is capped at 60,000 simulated packets per comparison and one million events per run.

## Interactive Packet Transfer

- DATA, ACK, CONTROL, VOICE and VIDEO are illustrative application-level traffic profiles with configurable payload sizes; they are not exact TCP/UDP/IP wire-protocol encodings.
- The transfer page replays a backend discrete-event simulation. It does not open sockets or transmit packets over a physical network.
- Per-packet payload and route-metadata modification scenarios are fault injections. Route-metadata alteration is recorded for the receiver report; it does not alter the simulator's router-selected forwarding state.
- Duplicate injection is represented as a duplicate observation at the destination and is counted separately from unique packet delivery.
- The interactive transfer currently uses one source/destination pair per batch and supports up to 100 packets per request.
- TCP connection semantics, retransmissions, application acknowledgements and packet reassembly are not modelled.

## Security

- Ed25519/SHA-256 remain optional authentication/integrity experiments only; the standalone Packet Security page is no longer part of the application navigation, and payload confidentiality is not provided.
- Keys are ephemeral; persistent key management, trust distribution, rotation and revocation are not implemented.
- Replay cache is per run and is not durable across restarts.
- Wall-clock signing/verification timings vary with hardware, OS, runtime, library version and system load.
- Legacy classroom RSA/token routes remain for compatibility and must not be confused with the Ed25519 research workflow.

## Experiment design and statistics

- Topology generation is deterministic for a seed; Erdős–Rényi graphs are forced connected by adding a spanning tree, so their distribution differs from an unconstrained G(n,p) sample.
- Small-world generation is a seeded ring-lattice rewiring variant, not a fully configurable Watts–Strogatz parameter sweep.
- Scale-free generation is a simple preferential-attachment variant with up to two links per new node.
- Variable traffic is a normalized Poisson-like arrival schedule, not an exact externally calibrated traffic distribution.
- A comparison supports one source/destination pair at a time.
- The current experiment form exposes scheduled failure selection for the active Network Studio graph. Generated topologies can be given failure schedules through the API, but the UI does not yet provide a generated-topology edge/node picker.
- Confidence intervals describe repeated simulator runs; they do not account for uncertainty in model assumptions or external validity.
- Detailed packet outcomes are stored in SQLite, while normal history responses return only per-run summary counts and metrics to keep responses small.

## Frontend validation status

The backend suite is executable and is reported in `TESTING_REPORT.md`. In the build environment used to prepare this archive, npm dependency installation did not complete, so the frontend production build and Vitest suite could not be confirmed here. The receiving Mac should run `npm install`, `npm test` and `npm run build` before relying on the UI for a formal demonstration.
