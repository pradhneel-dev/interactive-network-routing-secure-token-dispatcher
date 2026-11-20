from __future__ import annotations

from app.graph import Graph, demo_graph
from app.packet_security import Ed25519Identity, create_signed_packet, verify_signed_packet
from app.research import paired_comparison, simulate, summarize


def _config(**overrides):
    value = {
        "source": "Main Gate", "destination": "Data Center", "packet_count": 8,
        "duration_ms": 800.0, "packet_size_bytes": 512, "traffic_model": "constant",
        "ttl": 32, "failures": [], "security_enabled": False, "tamper_rate": 0.0,
        "duplicate_rate": 0.0, "packet_expiry_ms": 30000.0,
    }
    value.update(overrides)
    return value


def test_route_cost_and_propagation_delay_round_trip_independently():
    graph = Graph()
    graph.add_node("A")
    graph.add_node("B")
    graph.add_edge("A", "B", 7, propagation_delay_ms=123, capacity_mbps=25, loss_probability=0.1, queue_capacity_packets=9)
    exported = graph.to_dict()
    edge = exported["edges"][0]
    assert edge["weight"] == 7
    assert edge["propagation_delay_ms"] == 123
    restored = Graph.from_dict(exported)
    assert restored.adj["A"]["B"] == 7
    assert restored.get_edge_properties("A", "B")["propagation_delay_ms"] == 123
    assert restored.get_edge_properties("A", "B")["queue_capacity_packets"] == 9


def test_static_and_dynamic_dijkstra_behave_differently_after_link_failure():
    graph = demo_graph()
    # Freeze the initially selected route's first edge as the failure target.
    from app.research import _find_path
    path = _find_path(graph, "Main Gate", "Data Center", "dijkstra", set(), set())
    assert path and len(path) > 2
    config = _config(packet_count=5, duration_ms=1000, failures=[{
        "kind": "link", "u": path[0], "v": path[1], "at_ms": 0, "duration_ms": 500,
    }])
    static = simulate(graph.to_dict(), config, algorithm="dijkstra_static", seed=17, repetition=1)
    dynamic = simulate(graph.to_dict(), config, algorithm="dijkstra_dynamic", seed=17, repetition=1)
    assert static["metrics"]["dropped_link_failure"] > 0
    assert dynamic["metrics"]["network_delivered_packets"] == 5
    assert dynamic["metrics"]["route_recalculations"] > 0
    assert dynamic["metrics"]["route_recovery_ms"] is not None
    assert static["metrics"]["static_routing_table_entries"] == len(graph.nodes)


def test_simulation_repeats_logical_results_for_same_seed():
    graph = demo_graph()
    config = _config(packet_count=10, duration_ms=1000)
    a = simulate(graph.to_dict(), config, algorithm="dijkstra_static", seed=99, repetition=1)
    b = simulate(graph.to_dict(), config, algorithm="dijkstra_static", seed=99, repetition=1)
    assert a["metrics"] == b["metrics"]
    assert a["packet_outcomes"] == b["packet_outcomes"]


def test_ed25519_signature_detects_payload_tampering_and_replay():
    identity = Ed25519Identity.generate()
    signed = create_signed_packet(identity, "pkt-1", "A", "B", "content", 0, 500, nonce="nonce-1")
    seen = set()
    good = verify_signed_packet(signed, "content", arrival_at_ms=10, seen_nonces=seen)
    replay = verify_signed_packet(signed, "content", arrival_at_ms=11, seen_nonces=seen)
    tampered = verify_signed_packet(signed, "changed", arrival_at_ms=12, seen_nonces=set())
    assert good["valid"]
    assert replay["status"] == "replay_rejected"
    assert tampered["status"] == "payload_tampered"


def test_statistics_and_paired_differences_use_matched_repetitions():
    summary = summarize([1, 2, 3, 4])
    assert summary["n"] == 4 and summary["ci95"][0] < summary["mean"] < summary["ci95"][1]
    ref = [
        {"repetition": 1, "metrics": {"pdr": 0.5}},
        {"repetition": 2, "metrics": {"pdr": 0.7}},
    ]
    candidate = [
        {"repetition": 1, "metrics": {"pdr": 0.8}},
        {"repetition": 2, "metrics": {"pdr": 0.9}},
        {"repetition": 3, "metrics": {"pdr": 0.1}},
    ]
    result = paired_comparison(ref, candidate, "pdr")
    assert result["matched_repetitions"] == 2
    assert abs(result["mean"] - 0.25) < 1e-12


def test_student_t_critical_values_are_numerically_inverted():
    from app.research import _critical_t_975
    assert abs(_critical_t_975(1) - 12.7062047364) < 1e-8
    assert abs(_critical_t_975(30) - 2.0422724563) < 1e-8
    assert abs(_critical_t_975(60) - 2.0002978220) < 1e-8


def test_dynamic_routing_recovers_after_node_failure():
    graph = Graph()
    for node in ["S", "A", "B", "T"]:
        graph.add_node(node)
    graph.add_edge("S", "A", 1, propagation_delay_ms=1)
    graph.add_edge("A", "T", 1, propagation_delay_ms=1)
    graph.add_edge("S", "B", 3, propagation_delay_ms=1)
    graph.add_edge("B", "T", 3, propagation_delay_ms=1)
    config = _config(source="S", destination="T", packet_count=4, duration_ms=500,
                     failures=[{"kind": "node", "node": "A", "at_ms": 0, "duration_ms": 600}])
    frozen = simulate(graph.to_dict(), config, algorithm="dijkstra_static", seed=23, repetition=1)
    adaptive = simulate(graph.to_dict(), config, algorithm="dijkstra_dynamic", seed=23, repetition=1)
    assert frozen["metrics"]["network_delivered_packets"] == 0
    assert adaptive["metrics"]["network_delivered_packets"] == 4
    assert adaptive["metrics"]["route_recalculations"] > 0


def test_queue_overflow_and_ttl_are_classified_separately():
    graph = Graph()
    graph.add_node("A")
    graph.add_node("B")
    graph.add_edge("A", "B", 1, capacity_mbps=0.001, queue_capacity_packets=1)
    overflow = simulate(graph.to_dict(), _config(source="A", destination="B", packet_count=3,
                     duration_ms=100, packet_size_bytes=512), algorithm="dijkstra_static", seed=1, repetition=1)
    assert overflow["metrics"]["queue_overflows"] > 0
    assert overflow["metrics"]["dropped_queue_overflow"] > 0

    ttl_graph = Graph()
    for node in ["A", "B", "C"]:
        ttl_graph.add_node(node)
    ttl_graph.add_edge("A", "B", 1)
    ttl_graph.add_edge("B", "C", 1)
    expired = simulate(ttl_graph.to_dict(), _config(source="A", destination="C", packet_count=2,
                     duration_ms=100, ttl=1), algorithm="dijkstra_static", seed=1, repetition=1)
    assert expired["metrics"]["expired_packets"] == 2


def test_security_rejection_does_not_count_as_network_loss():
    graph = demo_graph()
    result = simulate(graph.to_dict(), _config(packet_count=4, duration_ms=800, security_enabled=True,
                    tamper_rate=1.0), algorithm="dijkstra_static", seed=6, repetition=1)
    metrics = result["metrics"]
    assert metrics["network_delivered_packets"] == 4
    assert metrics["security_rejected_packets"] == 4
    assert metrics["packet_delivery_ratio"] == 1.0
    assert metrics["verification_success_rate"] == 0.0


def test_paired_comparison_requires_matching_seed_when_available():
    reference = [{"repetition": 1, "seed": 10, "metrics": {"pdr": 0.5}}]
    candidate = [{"repetition": 1, "seed": 11, "metrics": {"pdr": 0.9}}]
    result = paired_comparison(reference, candidate, "pdr")
    assert result["matched_repetitions"] == 0
    assert result["mean"] is None


def test_generated_topology_families_are_connected_and_reproducible():
    from app.research import generate_topology
    for family in ("erdos_renyi", "small_world", "scale_free"):
        first = generate_topology(family, 20, 123)
        second = generate_topology(family, 20, 123)
        assert first.is_connected()
        assert first.to_dict() == second.to_dict()
        assert len(first.nodes) == 20
