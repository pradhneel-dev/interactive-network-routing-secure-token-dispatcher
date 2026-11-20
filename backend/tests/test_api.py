import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.state import STATE
from app.graph import demo_graph

c = TestClient(app)


@pytest.fixture(autouse=True)
def reset():
    STATE.replace_graph(demo_graph()); yield


def test_health_and_graph():
    assert c.get("/health").json()["status"] == "ok"
    g = c.get("/graph").json()
    assert len(g["nodes"]) == 8 and len(g["edges"]) == 13 and g["weights_simulated"] is True


def test_edit_errors_and_staleness_version():
    v = c.get("/graph").json()["version"]
    assert c.post("/graph/nodes", json={"id": "Annex"}).status_code == 201
    assert c.post("/graph/nodes", json={"id": "Annex"}).status_code == 409
    assert c.post("/graph/nodes", json={"id": " "}).status_code == 400
    assert c.post("/graph/edges", json={"u": "Annex", "v": "Annex", "weight": 1}).status_code == 400
    r = c.post("/graph/edges", json={"u": "Annex", "v": "Library", "weight": -1})
    assert r.status_code == 400 and r.json()["error"]["code"] == "negative_weight"
    assert c.post("/graph/edges", json={"u": "Annex", "v": "Library", "weight": 3}).status_code == 201
    assert c.get("/graph").json()["version"] > v
    assert c.delete("/graph/edges", params={"u": "Annex", "v": "Library"}).status_code == 200
    assert c.delete("/graph/nodes/Annex").status_code == 200
    assert c.delete("/graph/nodes/Nope").status_code == 404


def test_import_export_roundtrip_and_bad_import():
    exp = c.get("/graph/export").json()
    assert c.put("/graph", json=exp).status_code == 200
    assert c.put("/graph", json={"nodes": ["A"], "edges": [{"u": "A", "v": "B", "weight": 1}]}).status_code == 404
    assert len(c.get("/graph").json()["nodes"]) == 8  # failed import left graph intact


def test_routes_differ_bfs_vs_dijkstra():
    b = c.post("/routing/bfs", json={"source": "Main Gate", "target": "Data Center"}).json()
    d = c.post("/routing/dijkstra", json={"source": "Main Gate", "target": "Data Center"}).json()
    assert b["path"] != d["path"] and b["hops"] == 2 and d["cost"] == 9 and len(d["trace"]) > 3
    assert c.post("/routing/xyz", json={"source": "Main Gate", "target": "Data Center"}).status_code == 404
    assert c.post("/routing/bfs", json={"source": "Main Gate", "target": "Nowhere"}).status_code == 404


def test_analysis_endpoints():
    a = c.get("/graph/analysis").json()
    assert a["handshake"]["holds"] and a["connected"] and a["euler"]["classification"] == "none"
    assert c.get("/graph/hamiltonian", params={"kind": "path"}).json()["exists"] in (True, False)
    assert c.get("/graph/coloring").json()["valid"]
    assert c.post("/graph/traverse/dfs", json={"source": "Library"}).json()["traversal_order"][0] == "Library"
    c.post("/graph/sample", json={"nodes": 12, "seed": 1})
    assert c.get("/graph/hamiltonian").status_code == 422  # size guard


def test_full_dispatch_workflow_and_stale():
    r = c.post("/routing/dijkstra", json={"source": "Main Gate", "target": "Data Center"}).json()
    body = {"source": "Main Gate", "destination": "Data Center", "route": r["path"], "algorithm": "dijkstra",
            "payload": "hi", "count": 4}
    assert c.post("/packets/create", json=body).status_code == 201
    out = c.post("/packets/dispatch", json={"drop_seqs": [2], "tamper_payload_seqs": [3]}).json()
    rep = c.get("/packets/report").json()
    assert rep == out["report"] and rep["packets_lost"] == 1 and rep["integrity_failures"] == 1 and rep["delivered_verified"] == 2
    c.put("/graph/edges", json={"u": "Main Gate", "v": "Library", "weight": 1})
    assert c.post("/packets/dispatch", json={}).status_code == 409


def test_dispatch_without_batch():
    c.post("/packets/reset")
    assert c.post("/packets/dispatch", json={}).status_code == 409
    assert c.get("/packets/report").status_code == 404


def test_numtheory_and_tokens():
    assert c.post("/numtheory/gcd", json={"a": 48, "b": 18}).json()["gcd"] == 6
    assert c.post("/numtheory/egcd", json={"a": 240, "b": 46}).json()["verified"]
    assert c.post("/numtheory/modinv", json={"a": 6, "m": 9}).status_code == 400
    assert c.post("/numtheory/modexp", json={"base": 4, "exp": 13, "mod": 497}).json()["result"] == 445
    k = c.post("/rsa/keys", json={"p": 61, "q": 53, "e": 17}).json()
    ct = c.post("/rsa/encrypt", json={"value": 65, "n": k["n"], "key": 17}).json()["ciphertext"]
    assert c.post("/rsa/decrypt", json={"value": ct, "n": k["n"], "key": k["private"]["d"]}).json()["plaintext"] == 65
    t = c.post("/tokens/create", json={"source": "Library", "destination": "Hostel", "payload": "x"}).json()["token"]
    hdr = {k_: t[k_] for k_ in ("packet_id", "seq", "source", "destination", "route")}
    assert c.post("/tokens/verify", json={"token": t, "payload": "x", "packet_header": hdr}).json()["valid"]
    assert not c.post("/tokens/verify", json={"token": t, "payload": "y", "packet_header": hdr}).json()["valid"]


def test_math_endpoints():
    assert c.post("/math/backoff", json={"initial_delay": 100, "factor": 2, "steps": 5, "cap": 300}).json()["sequence"][-1] == 300
    assert c.post("/math/fibonacci", json={"n": 6}).json()["sequence"] == [0, 1, 1, 2, 3, 5, 8]
    assert c.post("/math/permutations", json={"n": 5, "k": 3}).json()["result"] == "60"
    assert c.post("/math/permutations", json={"n": 2, "k": 3}).status_code == 400
    assert c.post("/math/simple-paths", json={"source": "Main Gate", "target": "Data Center"}).json()["count"] > 0
    assert c.post("/math/additive", json={"initial": 100, "increment": 25, "steps": 2}).json()["sequence"] == [100, 125, 150]
    assert len(c.get("/math/concepts").json()) == 4


def test_research_api_experiment_persistence(monkeypatch, tmp_path):
    from app import research
    monkeypatch.setattr(research, "DB_PATH", tmp_path / "research-test.sqlite3")

    health = c.get("/health")
    assert health.status_code == 200 and health.json()["port"] == 8002

    response = c.post("/experiments/run", json={
        "algorithms": ["dijkstra_static", "dijkstra_dynamic"],
        "topology": "current", "source": "Main Gate", "destination": "Data Center",
        "packet_count": 4, "duration_ms": 100, "repetitions": 1, "seed": 7,
        "security_enabled": True,
    })
    assert response.status_code == 200, response.text
    comparison_id = response.json()["comparison_id"]
    assert set(response.json()["summaries"]) == {"dijkstra_static", "dijkstra_dynamic"}
    first_run = response.json()["runs"]["dijkstra_static"][0]
    assert first_run["packet_outcome_count"] == 4 and "packet_outcomes" not in first_run
    listed = c.get("/experiments").json()["experiments"]
    assert any(item["comparison_id"] == comparison_id and item["run_count"] == 2 for item in listed)
    detail = c.get(f"/experiments/{comparison_id}")
    assert detail.status_code == 200
    assert len(detail.json()["runs"]) == 2
    assert len(detail.json()["runs"][0]["topology"]["edges"]) == 13
    run_id = detail.json()["runs"][0]["run_id"]
    assert detail.json()["runs"][0]["result"]["packet_outcome_count"] == 4
    page = c.get(f"/experiments/runs/{run_id}/packets", params={"offset": 1, "limit": 2})
    assert page.status_code == 200
    assert page.json()["total"] == 4 and len(page.json()["packets"]) == 2
    assert page.json()["offset"] == 1
    assert c.get(f"/experiments/runs/{run_id}/packets", params={"limit": 501}).status_code == 422


def test_research_api_rejects_invalid_failure_schedule():
    response = c.post("/experiments/run", json={
        "algorithms": ["dijkstra_dynamic"], "topology": "current",
        "source": "Main Gate", "destination": "Data Center", "packet_count": 2,
        "duration_ms": 100, "repetitions": 1,
        "failures": [{"kind": "link", "u": "Main Gate", "v": "Not a link", "at_ms": 5, "duration_ms": 10}],
    })
    assert response.status_code == 422


def test_operational_graph_analysis_excludes_down_nodes_and_edges():
    assert c.post("/graph/nodes", json={"id": "DownNode", "x": 1, "y": 1}).status_code == 201
    assert c.post("/graph/edges", json={"u": "Main Gate", "v": "DownNode", "weight": 1, "status": "down"}).status_code == 201
    c.put("/graph", json={
        "nodes": [{"id": "A", "status": "up"}, {"id": "B", "status": "down"}],
        "edges": [{"u": "A", "v": "B", "weight": 1}],
    })
    operational = c.get("/graph/analysis").json()["operational"]
    assert operational["active_node_count"] == 1
    assert operational["active_edge_count"] == 0
    assert operational["failed_nodes"] == ["B"]


def test_node_ids_reject_unaddressable_path_characters():
    assert c.post("/graph/nodes", json={"id": "bad/name"}).status_code == 400
    assert c.post("/graph/nodes", json={"id": "x" * 65}).status_code == 400
