import pytest
from app.graph import (Graph, GraphError, bfs_trace, dfs_trace, dijkstra_trace, compute_route, demo_graph,
                       DEMO_PAIR, MAX_HAMILTONIAN_NODES)


def line(n=4):
    g = Graph()
    for i in range(n):
        g.add_node(f"N{i}")
    for i in range(n - 1):
        g.add_edge(f"N{i}", f"N{i+1}", 1)
    return g


def test_crud_and_validation():
    g = Graph()
    g.add_node("A"); g.add_node("B")
    g.add_edge("A", "B", 2)
    assert g.adj["A"]["B"] == g.adj["B"]["A"] == 2
    with pytest.raises(GraphError): g.add_node("A")
    with pytest.raises(GraphError): g.add_node("   ")
    with pytest.raises(GraphError): g.add_edge("A", "A", 1)
    with pytest.raises(GraphError) as e: g.add_edge("A", "B", -1)
    assert e.value.code in ("negative_weight", "duplicate_edge")
    g.add_node("C")
    with pytest.raises(GraphError) as e: g.add_edge("A", "C", -1)
    assert e.value.code == "negative_weight"
    with pytest.raises(GraphError): g.add_edge("A", "Z", 1)
    with pytest.raises(GraphError): g.add_edge("A", "B", 5)  # duplicate
    g.update_edge("A", "B", 9); assert g.adj["B"]["A"] == 9
    g.remove_edge("A", "B"); assert not g.has_edge("A", "B")
    g.remove_node("C"); assert "C" not in g.adj


def test_adjacency_degrees_handshake():
    g = demo_graph()
    labels = g.adjacency_matrix()["labels"]; m = g.adjacency_matrix()["matrix"]
    assert all(m[i][j] == m[j][i] for i in range(len(labels)) for j in range(len(labels)))
    assert sum(g.degree(n) for n in g.nodes) == 2 * len(g.edges()) == 26
    assert g.handshake()["holds"]
    assert len(g.nodes) == 8 and len(g.edges()) == 13
    assert g.adjacency_list()["Main Gate"][0]["node"] == "Administration Block"


def test_components_and_isolated():
    g = line(3); g.add_node("X")
    comps = g.components()
    assert len(comps) == 2 and not g.is_connected()
    assert g.analysis()["isolated_nodes"] == ["X"]
    assert demo_graph().is_connected()


def test_bfs_dfs_traversal():
    g = demo_graph()
    b = bfs_trace(g, "Main Gate"); d = dfs_trace(g, "Main Gate")
    assert set(b["traversal_order"]) == set(d["traversal_order"]) == set(g.nodes)
    assert b["traversal_order"][0] == "Main Gate"
    assert any(s["kind"] == "backtrack" for s in d["steps"])
    assert all("frontier" in s for s in b["steps"])


def test_euler_cases():
    g = Graph()
    for n in "ABC": g.add_node(n)
    g.add_edge("A", "B", 1); g.add_edge("B", "C", 1); g.add_edge("C", "A", 1)
    assert g.euler()["classification"] == "circuit"
    g.remove_edge("C", "A")
    assert g.euler()["classification"] == "trail"
    assert demo_graph().euler()["classification"] == "none"  # 4 odd vertices
    g2 = Graph()
    for n in "ABCD": g2.add_node(n)
    g2.add_edge("A", "B", 1); g2.add_edge("C", "D", 1)
    assert g2.euler()["classification"] == "none"  # disconnected edges
    g3 = line(3); g3.add_node("iso")
    assert g3.euler()["classification"] == "trail"  # isolated vertices ignored


def test_hamiltonian_and_guard():
    g = Graph()
    for n in "ABCD": g.add_node(n)
    for a, b in ("AB", "BC", "CD", "DA"): g.add_edge(a, b, 1)
    cyc = g.hamiltonian(True)
    assert cyc["exists"] and len(cyc["sequence"]) == 5 and cyc["sequence"][0] == cyc["sequence"][-1]
    assert line(5).hamiltonian(False)["exists"]
    assert not line(5).hamiltonian(True)["exists"]
    star = Graph()
    for n in ["c", "a", "b", "d"]: star.add_node(n)
    for n in "abd": star.add_edge("c", n, 1)
    assert not star.hamiltonian(False)["exists"]
    big = line(MAX_HAMILTONIAN_NODES + 1)
    with pytest.raises(GraphError) as e: big.hamiltonian(False)
    assert e.value.code == "size_guard"


def test_coloring_valid():
    g = demo_graph(); c = g.greedy_coloring()
    assert c["valid"] and all(c["colors"][u] != c["colors"][v] for u, v, _ in g.edges())
    assert Graph().greedy_coloring()["colors"] == {}


def test_bfs_min_hop_and_dijkstra_min_cost():
    g = demo_graph(); s, t = DEMO_PAIR
    b = compute_route(g, "bfs", s, t); d = compute_route(g, "dijkstra", s, t)
    assert b["hops"] == 2 and b["path"] == ["Main Gate", "Cafeteria", "Data Center"] and b["cost"] == 12
    assert d["cost"] == 9 and d["path"] == ["Main Gate", "Library", "Computer Lab", "Data Center"] and d["hops"] == 3
    assert b["path"] != d["path"]
    assert "DFS-found" in compute_route(g, "dfs", s, t)["label"]


def test_dfs_path_is_valid_but_labelled_not_shortest():
    g = demo_graph(); r = compute_route(g, "dfs", *DEMO_PAIR)
    assert r["found"] and r["path"][0] == "Main Gate" and r["path"][-1] == "Data Center"
    assert all(g.has_edge(a, b) for a, b in zip(r["path"], r["path"][1:]))


def test_dijkstra_matches_bruteforce():
    g = demo_graph()
    for t in g.nodes:
        r = compute_route(g, "dijkstra", "Main Gate", t)
        best = min(_all_costs(g, "Main Gate", t))
        assert r["cost"] == best


def _all_costs(g, s, t):
    out = []
    def go(u, seen, c):
        if u == t: out.append(c); return
        for v, w in g.adj[u].items():
            if v not in seen: go(v, seen | {v}, c + w)
    go(s, {s}, 0); return out


def test_unreachable_and_negative():
    g = line(2); g.add_node("X")
    for algo in ("bfs", "dfs", "dijkstra"):
        r = compute_route(g, algo, "N0", "X")
        assert r["found"] is False and r["path"] is None and "No route" in r["message"]
    g.adj["N0"]["N1"] = g.adj["N1"]["N0"] = -3  # corrupt on purpose
    with pytest.raises(GraphError) as e: dijkstra_trace(g, "N0", "N1")
    assert e.value.code == "negative_weight"


def test_dijkstra_trace_contents():
    t = dijkstra_trace(demo_graph(), "Main Gate", "Data Center")
    kinds = {s["kind"] for s in t["steps"]}
    assert {"init", "settle", "relax", "found"} <= kinds
    assert any(s.get("improved") for s in t["steps"]) and "distances" in t["steps"][-1]


def test_import_validation_and_roundtrip():
    g = demo_graph(); g2 = Graph.from_dict(g.to_dict())
    assert g2.edges() == g.edges()
    for bad in ({}, {"nodes": [""], "edges": []}, {"nodes": ["A", "A"], "edges": []},
                {"nodes": ["A", "B"], "edges": [{"u": "A", "v": "A", "weight": 1}]},
                {"nodes": ["A", "B"], "edges": [{"u": "A", "v": "B", "weight": -2}]}):
        with pytest.raises(GraphError): Graph.from_dict(bad)


def test_counting_helpers():
    g = demo_graph()
    assert g.count_simple_paths("Main Gate", "Data Center") > 3
    assert g.count_walks_exact("Main Gate", "Data Center", 2) == 1
    with pytest.raises(GraphError): line(11).count_simple_paths("N0", "N10")
