# Algorithm Documentation

## Graph representation

The active topology is an undirected weighted graph stored as an adjacency list:

`adjacency[node][neighbor] = routing_cost`

Each undirected edge has a separate simulation-property record containing propagation delay, capacity, loss probability, queue capacity and up/down status. Each node has an operational status. Graph import/export preserves these properties.

The graph editor rejects self-loops, duplicate edges, unknown endpoints and negative/non-finite routing costs. Node identifiers are limited to 64 characters and cannot contain `/`, `\\` or control characters so API path operations remain addressable.

## BFS

Breadth-first search uses a FIFO queue and explores neighbours in deterministic sorted order. In an unweighted graph it finds a minimum-hop path in `O(V + E)` time and `O(V)` auxiliary space. In this project, BFS is a minimum-hop baseline and ignores routing-cost weights.

## DFS

Depth-first search explores as far as possible along a branch before backtracking. It is included in the interactive routing workspace to demonstrate traversal order and stack/recursion behavior. DFS does not guarantee a shortest path.

## Dijkstra

Dijkstra uses a min-priority queue and non-negative routing costs. The implementation computes minimum-cost paths. Negative routing costs are rejected by the graph model.

### Static Dijkstra in the research simulator

At simulation time zero, the simulator computes a destination-specific forwarding entry for every node in the initial graph. Each entry is a minimum-cost route from that router to the selected destination. Those entries are frozen for the entire run. If a scheduled failure makes a stored next hop unavailable, static routing does not recompute; the packet is dropped under the configured failure model.

This is a single-destination slice of a forwarding table, not an all-destination routing-table simulation.

### Dynamic Dijkstra in the research simulator

Dynamic Dijkstra selects a path from the packet's current node using the current operational graph. It caches the path until the topology version changes. A scheduled link/node failure or recovery changes the version and causes a fresh route calculation for packets that need to forward again.

## Research comparison scope

Primary experiment algorithms:

1. BFS (minimum-hop baseline on an unweighted interpretation).
2. Static Dijkstra (frozen time-zero forwarding entries).
3. Dynamic Dijkstra (recalculation after supported topology changes).

ARAR is not included in the primary comparisons. The legacy frontend route workspace still exposes DFS for educational traversal; DFS is not an experiment option.

## Complexity interpretation

The classical BFS/DFS bound is `O(V + E)` for adjacency-list graph traversal. Dijkstra complexity depends on the priority queue and implementation details; this project uses a binary heap and adjacency list, conventionally `O((V + E) log V)` for non-negative edge costs. The exact measured runtime of a run depends on the Python runtime, machine, topology and simulation load.

The discrete-event simulator's total work also includes packet events, queue operations, routing recalculations, failure events and security checks. It should not be described by the graph algorithm complexity alone.
