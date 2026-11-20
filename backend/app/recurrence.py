"""Recurrence relations and counting (Unit 4)."""
from __future__ import annotations

from typing import Any

MAX_TERMS = 1000


class MathInputError(ValueError):
    def __init__(self, message: str, code: str = "invalid_input", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _steps(n: int) -> int:
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise MathInputError("Number of steps must be a non-negative integer.")
    if n > MAX_TERMS:
        raise MathInputError(f"At most {MAX_TERMS} steps are allowed.")
    return n


def additive_growth(initial: float, increment: float, steps: int) -> dict[str, Any]:
    _steps(steps)
    seq = [initial]
    for _ in range(steps):
        seq.append(seq[-1] + increment)
    return {"model": "additive", "formula": "T_n = T_(n-1) + k  =>  T_n = T_0 + n k",
            "sequence": seq, "unit": "packets per interval (assumed)",
            "assumptions": "Traffic grows by a fixed amount k each interval."}


def exponential_backoff(initial_delay: float, factor: float, steps: int, cap: float | None = None) -> dict[str, Any]:
    _steps(steps)
    if initial_delay < 0 or factor < 0:
        raise MathInputError("Initial delay and multiplier must be non-negative.")
    if cap is not None and cap < 0:
        raise MathInputError("Cap must be non-negative.")
    seq = [initial_delay if cap is None else min(initial_delay, cap)]
    for _ in range(steps):
        nxt = factor * seq[-1]
        seq.append(nxt if cap is None else min(nxt, cap))
    capped_at = next((i for i, v in enumerate(seq) if cap is not None and v >= cap), None)
    return {"model": "backoff", "formula": "D_n = min(r x D_(n-1), cap)" if cap is not None else "D_n = r x D_(n-1)",
            "sequence": seq, "unit": "time units (e.g. ms)", "capped_at_retry": capped_at,
            "assumptions": "Delay is multiplied by r after each failed retry; the cap bounds the delay."}


def fibonacci(n: int, f0: int = 0, f1: int = 1) -> dict[str, Any]:
    _steps(n)
    seq = [f0, f1][: n + 1]
    while len(seq) < n + 1:
        seq.append(seq[-1] + seq[-2])
    return {"model": "fibonacci", "formula": f"F_n = F_(n-1) + F_(n-2), F_0 = {f0}, F_1 = {f1}",
            "sequence": [str(v) if abs(v) > 2**53 else v for v in seq], "unit": "count",
            "assumptions": "Explicit initial conditions are required for a second-order recurrence."}


def walk_count_regular(degree: int, steps: int) -> dict[str, Any]:
    _steps(steps)
    if not isinstance(degree, int) or degree < 0:
        raise MathInputError("Branching factor d must be a non-negative integer.")
    seq = [1]
    for _ in range(steps):
        seq.append(degree * seq[-1])
    return {"model": "walks", "formula": "P_n = d x P_(n-1), P_0 = 1  =>  P_n = d^n",
            "sequence": [str(v) if v > 2**53 else v for v in seq], "result": str(degree ** steps), "unit": "walks",
            "assumptions": "ONLY valid when every vertex offers exactly d choices (regular branching, walks may revisit "
                           "vertices). It is NOT a universal formula for arbitrary graphs."}


def k_permutations(n: int, k: int) -> dict[str, Any]:
    if n < 0 or k < 0 or k > n or n > 10_000:
        raise MathInputError("Require 0 <= k <= n (n <= 10000).")
    result = 1
    for i in range(k):
        result *= n - i
    return {"model": "permutations", "formula": "P(n,k) = n!/(n-k)! = n(n-1)...(n-k+1)",
            "result": str(result), "n": n, "k": k, "unit": "ordered selections",
            "assumptions": "Ordered selections of k distinct items from n."}


CONCEPTS = [
    {"term": "Walk", "meaning": "Sequence of adjacent vertices; vertices and edges may repeat. Counted by powers of the adjacency matrix."},
    {"term": "Simple path", "meaning": "A walk with no repeated vertex. Counting is exponential in the worst case, so it is size-guarded."},
    {"term": "Minimum-hop route", "meaning": "Fewest edges between two vertices (BFS); ignores weights."},
    {"term": "Minimum-cost route", "meaning": "Smallest total weight (Dijkstra, non-negative weights); may use more hops than the minimum-hop route."},
]
