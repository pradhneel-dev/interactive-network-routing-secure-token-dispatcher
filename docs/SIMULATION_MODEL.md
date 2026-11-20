# Discrete-Event Simulation Model

## Scope

The simulator models a simplified undirected packet network. It is a controlled software model, not a real protocol stack, hardware router, network emulator or packet-capture system.

## Topology and link properties

Each undirected link stores:

- `weight`: routing cost used by Dijkstra.
- `propagation_delay_ms`: propagation delay added after link serialization.
- `capacity_mbps`: link bit rate used to calculate serialization time.
- `loss_probability`: independent per-hop loss probability, selected deterministically from seed/packet/link/hop material.
- `queue_capacity_packets`: maximum occupancy for that directed output queue, including a packet currently being serialized.
- `status`: `up` or `down`.

Each physical link has separate FIFO queues for its two directions, representing full-duplex transmission. This is a modelling assumption, not a detailed physical-layer model.

## Event ordering

The event engine processes a priority queue ordered by simulation time, event priority and insertion sequence. Failure state changes at the same timestamp are applied before packet generation and transmission completion events. This ensures a failure scheduled at `t=0` is in effect before packets are generated at `t=0`.

## Packet lifecycle

Packets are generated according to one of three arrival patterns:

- Constant: evenly spaced within the traffic window.
- Variable: deterministic Poisson-like inter-arrival gaps generated from a seeded exponential distribution and normalized to the configured duration.
- Burst: packets grouped into up to three time clusters.

A packet is routed hop by hop. At each directed link it enters the FIFO queue if the link is operational and queue occupancy is below capacity. When its serializer becomes available, serialization delay is:

`serialization_ms = packet_size_bytes * 8 / (capacity_mbps * 1,000,000) * 1000`

The packet then waits the configured `propagation_delay_ms` before its arrival event is processed at the next node.

### Per-packet loss scenario and edge visualization

The Packet Transfer page's per-packet `drop` scenario is an in-flight fault, not a packet that is omitted before dispatch. To match the original IRSD packet dispatcher, the simulator selects a middle route edge using `max(0, (route_node_count - 2) // 2)` successful hops before the loss edge. The packet completes earlier hops normally, enters the FIFO queue for the selected edge, completes link serialization and waits that edge's propagation delay. It is then recorded as lost before the receiving node processes it.

The trace contains `transmitting`, `serialization_complete`, and `packet_lost_on_link` events with both endpoints of the loss edge. During replay, the edge is highlighted dark red and labelled with the lost packet ID. Stepping backward before the loss event removes that red marker; stepping forward restores it. The packet's `route_history` contains nodes it reached, while `edge_attempts` and `lost_on_edge` identify the final edge it attempted but did not reach across.

Seeded `loss_probability` outcomes use the same in-flight timing: the packet is serialized and propagates on the edge before the simulator records loss. Queue overflow and failures that prevent transmission remain distinct outcomes and do not falsely appear as an in-flight packet loss.

No separate per-node processing delay is currently modelled.

## Failure model

Experiments can schedule temporary link or node failures with start time and positive duration.

- Failure start must fall inside the configured traffic-generation window.
- Overlapping windows for the same exact resource are rejected.
- A link failure interrupts a serialization event that overlaps the failure (via a link-generation counter).
- A packet whose transmission has completed and is already in propagation is allowed to arrive; the link failure does not reverse propagation already in flight.
- A node failure invalidates adjacent in-service transmissions and drains adjacent queues according to the routing strategy.
- Static Dijkstra keeps its frozen entry and may drop packets.
- Dynamic Dijkstra recalculates from the current node when forwarding resumes after a topology change.

Failure duration can extend beyond the traffic-generation window; the simulator continues processing scheduled completion/recovery events needed by packets already in flight.

## Queueing and packet terminal states

Terminal statuses are classified separately:

- `delivered`
- `dropped_link_failure`
- `dropped_node_failure`
- `dropped_link_loss`
- `dropped_simulated` (per-packet test loss injected on a selected route edge after serialization and propagation)
- `dropped_queue_overflow`
- `dropped_no_route`
- `expired_packets` (TTL exhausted)
- `security_rejected_packets` (network delivery occurred but packet authentication failed)

Network delivery and authentication acceptance are separate. A security-rejected packet counts as having reached the destination for network PDR, but it does not count as authenticated.

## TTL

Before a packet is forwarded from its current node, the hop count is checked against TTL. If the hop count is at least TTL, it is classified as expired. A packet may complete a path containing exactly TTL links because the destination check occurs after arrival.

## Reproducibility

A comparison reuses one topology snapshot for all algorithms. Each repetition uses `base_seed + repetition_index` for every algorithm. Variable traffic and loss/tampering/replay injection decisions are deterministic for a fixed seed and input. The logical network outcomes should therefore be reproducible for identical snapshots/configuration/seeds.

Cryptographic timing fields are measured using local wall-clock timers and will vary between runs and machines even when logical outcomes match.

## Measurement window and metrics

The measurement window is at least the configured traffic-generation duration and extends to the latest packet terminal time if packet completion occurs later. Throughput is network-delivered payload bits divided by this measurement window. It excludes protocol headers and control-plane overhead.

PDR is network-delivered packets / generated packets. Security rejection remains a separate metric and does not retroactively count a network-delivered packet as packet loss.

Latency samples include packets that reached the destination, including those rejected by authentication. The recovery-time metric is defined in `METRIC_DEFINITIONS.md`.

## Current limitations

- Undirected topology only.
- No TCP congestion control, retransmission protocol or routing-control packet exchange.
- No separate processing delay, CPU utilization or memory utilization measurement.
- No real hardware, wireless, propagation medium or OS networking effects.
- No flow multiplexing model beyond the configured FIFO link queues.
- Link propagation already in flight is not interrupted by a failure.
- Static routing freezes one destination-specific entry per router, not all destinations concurrently.
- Synchronous API execution is capped; long experiments can block the request.
