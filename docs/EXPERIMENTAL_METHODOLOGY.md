# Experimental Methodology

## Research direction

The platform supports empirical evaluation of routing under failures and selected traffic conditions, plus an evaluation of Ed25519/SHA-256 packet-authentication overhead in the local simulator.

The system does not claim a novel routing algorithm. It is an experimental platform for comparing defined mechanisms under controlled inputs.

## Research questions

1. How do static and dynamic Dijkstra differ in delivery, delay and route recovery under timed node/link failures?
2. How do constant, variable and burst traffic patterns affect delivery, throughput and latency?
3. How do topology family and node count affect route exploration and observed outcomes?
4. How does the first successful delivery after an adaptive route change occur relative to the first failure event?
5. What local signing and verification overhead is observed when Ed25519/SHA-256 authentication is enabled?

## Experimental variables

### Independent variables

- Algorithm: BFS, Static Dijkstra, Dynamic Dijkstra.
- Topology family: current, Erdős–Rényi connected random, small-world, scale-free.
- Node count for generated graphs.
- Traffic pattern: constant, variable/Poisson-like, burst.
- Packet count, packet size and traffic duration.
- Link capacity, propagation delay, loss probability and queue capacity embedded in topology.
- Failure type, resource and timing.
- Security enabled/disabled, payload tamper rate and duplicate/replay injection rate.

### Dependent variables

- Packet delivery ratio and loss ratio.
- Throughput.
- Mean, median and 95th-percentile end-to-end latency.
- Route recovery time and recalculation count.
- Queue overflow and cause-specific drops.
- Ed25519 signing and verification latency.
- Verification success rate and security rejection count.

### Controlled variables

Within a matched comparison, algorithms share the same topology snapshot, source/destination, packet generation schedule, packet size, TTL, failure schedule, security settings and repetition seed. The algorithm is the intended changed variable.

## Topology generation

- `current`: an immutable snapshot of the graph currently held in the backend.
- `erdos_renyi`: random edge selection with a deterministic seed; a spanning tree is added to ensure a connected starting graph.
- `small_world`: ring-lattice base with seeded rewiring.
- `scale_free`: preferential-attachment construction with up to two attachments per newly added node.

Generated graphs are undirected. Every generated edge receives deterministic routing cost and propagation-delay inputs. The topology JSON is saved for each run.

## Traffic generation

- Constant rate uses evenly spaced packet generation times.
- Variable traffic uses seeded exponential gaps normalized to the experiment window. This is a Poisson-like arrival pattern, not a continuous-time statistical traffic generator.
- Burst traffic divides packets into up to three temporal clusters.

All algorithms in a repetition receive identical packet generation times because the same seed and configuration are used.

## Failure modelling

Failure schedules identify a link or node, a start time and a duration. The start time must be within the traffic generation window. Same-resource overlapping schedules are rejected. The failure event changes the simulator topology version; dynamic routes adapt when packets resume forwarding. Static forwarding entries remain frozen.

## Repetitions and paired design

For repetition `r`, the run seed is `base_seed + r - 1`. The same seed is used for every algorithm in that repetition. Paired differences are calculated only for observations that match both repetition index and seed.

The default comparison uses Static Dijkstra as reference when it is included; otherwise the first selected algorithm becomes the reference. Paired differences are candidate minus reference.

## Statistical analysis

For each metric, the backend reports sample count, mean, sample standard deviation, median and a 95% confidence interval when at least two observations exist. The t critical value is numerically obtained by inverting the Student-t tail probability using the regularized incomplete beta function. At `n=1`, no confidence interval is reported.

Paired comparisons summarize the per-repetition candidate-minus-reference differences. They do not imply causality beyond the controlled simulation conditions.

## Provenance

Every saved run records:

- Experiment and run identifiers.
- Algorithm, repetition and seed.
- Full topology snapshot.
- Experiment configuration and failure schedule.
- Metric results and packet outcomes.
- Timestamp and application version.
- Python/platform and selected backend package versions.

Logical simulation outcomes are deterministic for a fixed snapshot/configuration/seed. Wall-clock cryptographic timings are not expected to be identical.

## Interpretation

The results describe this simulator under its explicit assumptions. They cannot be generalized directly to physical networks without validation against real traffic, network devices or an independently validated simulator. Report all parameter settings and limitations with results.
