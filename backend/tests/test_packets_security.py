import pytest
from app.graph import demo_graph, compute_route, DEMO_PAIR, GraphError
from app.security import KeyRegistry, create_token, verify_token
from app import packets as P


@pytest.fixture(scope="module")
def reg():
    return KeyRegistry(bits=32)


def make(reg, count=4, algo="dijkstra"):
    g = demo_graph(); r = compute_route(g, algo, *DEMO_PAIR)
    return g, P.create_batch(g, reg, 1, DEMO_PAIR[0], DEMO_PAIR[1], r["path"], algo, "hello", count)


def run(reg, count=4, **opts):
    g, b = make(reg, count)
    return b, P.dispatch(g, reg, b, opts)


def test_valid_token_and_nonce(reg):
    t = create_token(reg, "X-1", 1, "Library", "Hostel", ["Library", "Hostel"], "data")
    v = verify_token(reg, t, "data", {k: t[k] for k in ("packet_id", "seq", "source", "destination", "route")})
    assert v["valid"] and v["status"] == "Delivered & Verified"
    assert v["checks"]["nonce_recovered"] is not None


def test_invalid_token_never_valid(reg):
    t = create_token(reg, "X-2", 1, "Library", "Hostel", ["Library", "Hostel"], "data")
    hdr = {k: t[k] for k in ("packet_id", "seq", "source", "destination", "route")}
    assert not verify_token(reg, {**t, "signature": t["signature"] + 1}, "data", hdr)["valid"]
    assert not verify_token(reg, {**t, "route": ["Library", "Cafeteria", "Hostel"]}, "data", hdr)["valid"]
    assert not verify_token(reg, {**t, "payload_digest": "0" * 64}, "data", hdr)["valid"]
    assert not verify_token(reg, {**t, "encrypted_nonce": t["encrypted_nonce"] + 1}, "data", hdr)["valid"]
    assert not verify_token(reg, t, "data!", hdr)["valid"]


def test_normal_batch_delivered_and_verified(reg):
    b, out = run(reg, 5)
    rep = out["report"]
    assert rep["packets_sent"] == 5 and rep["packets_received"] == 5 and rep["packets_lost"] == 0
    assert rep["delivered_verified"] == 5 and rep["delivery_percentage"] == 100.0
    assert rep["integrity_failures"] == rep["signature_failures"] == rep["metadata_failures"] == 0
    assert rep["route"] == ["Main Gate", "Library", "Computer Lab", "Data Center"] and rep["cost"] == 9 and rep["hops"] == 3


def test_dropped_packet_detected_by_missing_id(reg):
    b, out = run(reg, 4, drop_seqs=[2])
    rep = out["report"]
    assert rep["lost_ids"] == [b["packets"][1]["packet_id"]] and rep["packets_lost"] == 1
    assert rep["packets_received"] == 3 and rep["delivered_verified"] == 3 and rep["delivery_percentage"] == 75.0
    lost = next(r for r in out["results"] if r["seq"] == 2)
    assert lost["status"] == "Lost/Missing" and lost["checks"] is None   # no payload to hash
    assert rep["integrity_failures"] == 0                                 # loss is not integrity failure


def test_drop_count_option(reg):
    _, out = run(reg, 5, drop_count=2)
    assert out["report"]["packets_lost"] == 2 and out["options_applied"]["dropped_seqs"] == [4, 5]


def test_payload_tamper_fails_integrity_only(reg):
    _, out = run(reg, 3, tamper_payload_seqs=[1])
    r = next(x for x in out["results"] if x["seq"] == 1)
    assert r["status"] == "Payload Modified" and not r["verified"]
    assert r["checks"]["signature_valid"] and not r["checks"]["digest_matches"]
    rep = out["report"]; assert rep["integrity_failures"] == 1 and rep["delivered_verified"] == 2 and rep["packets_lost"] == 0


def test_route_tamper_fails_metadata_check(reg):
    _, out = run(reg, 3, tamper_route_seqs=[3])
    r = next(x for x in out["results"] if x["seq"] == 3)
    assert r["status"] == "Metadata Tampered" and not r["verified"]
    assert r["checks"]["signature_valid"] is True and r["checks"]["metadata_signature_valid"] is False
    assert any("route" in s for s in r["reasons"]) and out["report"]["metadata_failures"] == 1


def test_token_signature_tamper(reg):
    _, out = run(reg, 2, tamper_token_seqs=[2])
    r = next(x for x in out["results"] if x["seq"] == 2)
    assert r["status"] == "Signature Invalid" and out["report"]["signature_failures"] == 1


def test_duplicate_is_ignored_not_double_counted(reg):
    _, out = run(reg, 2, duplicate_seqs=[1])
    rep = out["report"]
    assert rep["duplicates_ignored"] == 1 and rep["packets_received"] == 2 and rep["delivered_verified"] == 2


def test_combined_scenario_report_consistency(reg):
    _, out = run(reg, 5, drop_seqs=[2], tamper_payload_seqs=[3], tamper_route_seqs=[4])
    rep = out["report"]
    assert rep["packets_sent"] == 5 and rep["packets_lost"] == 1 and rep["packets_received"] == 4
    assert rep["delivered_verified"] == 2 and rep["integrity_failures"] == 1 and rep["metadata_failures"] == 1
    assert rep["delivery_percentage"] == 40.0
    assert sum(1 for r in out["results"] if r["verified"]) == rep["delivered_verified"]


def test_events_follow_actual_route(reg):
    b, out = run(reg, 2)
    for p in b["packets"]:
        hops = [e for e in out["events"] if e["packet_id"] == p["packet_id"] and e["kind"] == "hop"]
        assert [hops[0]["from"]] + [h["to"] for h in hops] == b["route"]
        assert [h["hop"] for h in hops] == list(range(1, len(b["route"])))


def test_validation_errors(reg):
    g, b = make(reg, 2)
    with pytest.raises(GraphError): P.create_batch(g, reg, 1, "Main Gate", "Main Gate", ["Main Gate"], "bfs", "x", 1)
    with pytest.raises(GraphError): P.create_batch(g, reg, 1, "Main Gate", "Data Center", b["route"], "bfs", "  ", 1)
    with pytest.raises(GraphError): P.create_batch(g, reg, 1, "Main Gate", "Data Center", ["Main Gate", "Data Center"], "bfs", "x", 1)
    with pytest.raises(GraphError): P.dispatch(g, reg, b, {"drop_seqs": [99]})
    g.remove_edge("Library", "Computer Lab")
    with pytest.raises(GraphError) as e: P.dispatch(g, reg, b, {})
    assert e.value.code == "stale_route"
