# Research Paper Outline (Proposed)

## Working title

**An Interactive Discrete-Event Platform for Evaluating Network Routing, Packet Transfer and Resilience under Controlled Failures**

This title describes an evaluation platform and existing mechanisms. It does not claim a novel routing algorithm.

## Abstract structure

1. Problem: fixed routing decisions can become unusable after topology failures.
2. Approach: implement a reproducible discrete-event network simulator with static and adaptive Dijkstra and a BFS minimum-hop baseline.
3. Method: matched topology, traffic, failure schedules and random seeds across repeated runs.
4. Packet-transfer capability: generate mixed DATA, ACK, CONTROL, VOICE and VIDEO traffic profiles, inject selected per-packet faults, and replay hop-by-hop simulation traces. Optional Ed25519/SHA-256 authentication experiments can measure local computational overhead.
5. Results: report measured outcomes only after completing experiments and validating metric calculations.
6. Limitations: simplified simulator model and absence of physical network validation.

## 1. Introduction

- Motivation for studying routing resilience and packet authentication.
- Research questions and scope.
- Explicit statement that the project evaluates existing algorithms rather than proposing a novel routing algorithm.

## 2. Related Work

- Shortest-path routing and Dijkstra.
- Minimum-hop routing and BFS.
- Adaptive rerouting/failure recovery.
- Event-driven network simulation.
- Ed25519 and authenticated packet integrity.

Add only verified scholarly references. Do not invent citations or state unsupported literature conclusions.

## 3. System Design

- Graph and link-property model.
- Static destination-specific forwarding entries.
- Dynamic route recalculation.
- Discrete-event engine and FIFO queues.
- Mixed packet-profile generation, per-packet fault injection and transfer event trace.
- Experiment provenance and SQLite storage.

## 4. Experimental Methodology

- Research questions, independent/dependent/controlled variables.
- Topology families and graph sizes.
- Traffic patterns, packet sizes and duration.
- Node/link failure schedules.
- Matched seeds and repetitions.
- Security-enabled/disabled conditions.
- Statistical analysis and confidence intervals.

## 5. Results

Populate only after running controlled experiments. Suggested figures:

- PDR vs failure timing.
- Throughput vs offered traffic.
- Mean/median/p95 latency by algorithm.
- Route recovery observations.
- Performance vs node count/topology family.
- Ed25519 signing and verification latency distribution.

Include sample size, seed policy, confidence intervals and parameter settings with each figure.

## 6. Discussion

- Explain observed differences in the context of the implemented model.
- Distinguish route recalculation behavior from real control-plane convergence.
- Discuss trade-offs in delivery, latency and authentication overhead.

## 7. Limitations and Threats to Validity

- Model abstraction and external validity.
- Single source/destination per experiment.
- Undirected graph restriction.
- Simplified traffic/channel model.
- Environment-dependent cryptographic timings.
- Repetition count and statistical uncertainty.

## 8. Conclusion and Future Work

Summarize empirical findings only after the study is complete. Possible future work: directed graphs, background simulation jobs, validated network emulation, multi-flow traffic, processing delay, CPU/memory profiling and persistent key management.
