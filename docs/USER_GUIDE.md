# User Guide

## Start the application

1. Start FastAPI in `backend` on `127.0.0.1:8002`.
2. Start Vite in `frontend` on `127.0.0.1:5174`.
3. Open `http://127.0.0.1:5174`.

Detailed commands are in the root `README.md`.

## Prepare a network

1. Open **Network Studio**.
2. Load the demo topology or generate a sample.
3. Add/move/delete nodes or edit links.
4. Set Routing Cost, Propagation Delay (ms), Capacity (Mbps), and Loss Probability separately.
5. Export the graph JSON if you want to keep a portable copy.

## Inspect a route

1. Open **Routing & Resilience**.
2. Choose source and destination.
3. Select BFS, DFS or Dijkstra for the interactive trace.
4. Inspect the route and trace panel.
5. Use play/pause/next/reset to inspect queue, stack or priority-queue states.

## Evaluate resilience

1. Open **Experiments**.
2. Select BFS, Static Dijkstra and/or Dynamic Dijkstra.
3. Choose current graph or a generated topology family.
4. Set traffic, packet count, duration, repetition count and seed.
5. Optionally add a timed link or node failure when using the current topology.
6. Choose whether Ed25519 authentication and tamper/replay injections are enabled.
7. Run the matched comparison.

Static Dijkstra freezes the initial destination-specific forwarding entries. Dynamic Dijkstra recalculates after topology changes. BFS ignores routing costs and acts as an unweighted minimum-hop baseline.

## Review results

Open **Results & Analytics** to review per-run metrics, aggregate summaries, confidence intervals, paired differences and topology/configuration provenance. Export JSON or CSV for analysis.

## Create and transfer packets

Open **Packet Transfer** after loading a topology in Network Studio.

1. Select a source node, destination node and routing strategy (BFS, Static Dijkstra or Dynamic Dijkstra).
2. Enter a payload template. A class label and unique packet ID are appended to each created packet.
3. Choose a traffic mix from DATA, ACK, CONTROL, VOICE and VIDEO. Each class has an editable packet size; these are illustrative traffic profiles, not exact wire-protocol implementations.
4. Set the packet count and byte size for each class, traffic pattern, TTL, duration and random seed.
5. Create the packet batch. Every packet receives an individual ID and can be configured for normal delivery, loss on a route edge, payload modification, route-metadata alteration or duplicate arrival. A selected packet-loss scenario is not skipped: it traverses earlier hops, enters the selected edge's queue, is serialized and propagates across that edge, then is lost before reaching the next node. The loss edge is highlighted dark red with the packet ID during replay.
6. Optionally schedule a temporary link or node failure. Use the same failure and seed to compare Static Dijkstra (frozen time-zero forwarding entries) with Dynamic Dijkstra (recalculation after topology changes).
7. Start the transfer. The backend discrete-event simulator processes queueing, serialization, propagation delay, link loss, TTL and failures. The frontend replays the resulting event trace; it does not send real network traffic.
8. Use Play, Pause, Step, Replay or Skip to inspect packet movement. A yellow edge label shows the packet currently transmitting; a dark-red edge label identifies the edge where a packet was lost. The graph also marks failed resources and packets waiting at simulated nodes.
9. Review the transmission report for delivered/lost packets, delivery ratio, latency, throughput, hop attempts, serialized bytes, duplicates, each lost edge and individual route histories. Export the transfer JSON for later inspection.

Payload and route-metadata modifications are fault-injection demonstrations. They are not cryptographic verification. Optional Ed25519/SHA-256 authentication remains available as an experimental variable in the Experiments module, not as a separate static Packet Security page.

## Interpret the measurements

Use **Methodology** and the matching documents in `docs/`. Results describe the local simulator and its assumptions; they are not physical network measurements.
