import pytest
from app import recurrence as R
from app.graph import demo_graph


def test_additive():
    assert R.additive_growth(100, 25, 4)["sequence"] == [100, 125, 150, 175, 200]


def test_backoff_and_cap():
    assert R.exponential_backoff(100, 2, 4)["sequence"] == [100, 200, 400, 800, 1600]
    r = R.exponential_backoff(100, 2, 6, cap=500)
    assert r["sequence"] == [100, 200, 400, 500, 500, 500, 500] and r["capped_at_retry"] == 3
    with pytest.raises(R.MathInputError): R.exponential_backoff(-1, 2, 3)


def test_fibonacci():
    assert R.fibonacci(10)["sequence"] == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
    assert R.fibonacci(4, 2, 1)["sequence"] == [2, 1, 3, 4, 7]
    with pytest.raises(R.MathInputError): R.fibonacci(-1)


def test_walks_assumption_and_exact():
    assert R.walk_count_regular(3, 4)["result"] == "81" and R.walk_count_regular(3, 4)["sequence"] == [1, 3, 9, 27, 81]
    assert "NOT a universal" in R.walk_count_regular(2, 2)["assumptions"]
    g = demo_graph()  # irregular graph: d^n does not match the exact count
    assert g.count_walks_exact("Main Gate", "Data Center", 2) != 3 ** 2


def test_permutations():
    assert R.k_permutations(5, 2)["result"] == "20" and R.k_permutations(5, 0)["result"] == "1"
    assert R.k_permutations(6, 6)["result"] == "720"
    with pytest.raises(R.MathInputError): R.k_permutations(3, 4)


def test_simple_path_count_square():
    from app.graph import Graph
    g = Graph()
    for n in "ABCD": g.add_node(n)
    for a, b in ("AB", "BC", "CD", "DA"): g.add_edge(a, b, 1)
    assert g.count_simple_paths("A", "C") == 2
