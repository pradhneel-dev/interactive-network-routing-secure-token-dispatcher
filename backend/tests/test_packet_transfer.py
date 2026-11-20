from fastapi.testclient import TestClient

from app.graph import compute_route, demo_graph
from app.main import app
from app.state import STATE

client = TestClient(app)


def setup_function():
    STATE.replace_graph(demo_graph())


def base_payload(**overrides):
    payload = {
        "source": "Main Gate",
        "destination": "Data Center",
        "algorithm": "dijkstra_dynamic",
        "duration_ms": 1200,
        "traffic_model": "constant",
        "ttl": 24,
        "seed": 17,
        "packet_profiles": [
            {"packet_type": "data", "size_bytes": 512, "payload": "application data", "scenario": "normal"},
            {"packet_type": "ack", "size_bytes": 64, "payload": "acknowledged", "scenario": "normal"},
            {"packet_type": "control", "size_bytes": 128, "payload": "routing update", "scenario": "normal"},
            {"packet_type": "video", "size_bytes": 1400, "payload": "video frame", "scenario": "normal"},
        ],
        "failures": [],
    }
    payload.update(overrides)
    return payload


def test_packet_transfer_creates_multiple_traffic_classes_and_trace():
    response = client.post("/packets/transfer", json=base_payload())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["packet_count"] == 4
    assert [packet["packet_type"] for packet in result["packets"]] == ["data", "ack", "control", "video"]
    assert [packet["size_bytes"] for packet in result["packets"]] == [512, 64, 128, 1400]
    assert result["metrics"]["delivered_bytes"] == sum(p["size_bytes"] for p in result["packets"] if p["status"] == "delivered")
    assert any(event["kind"] == "generated" for event in result["trace_events"])
    assert any(event["kind"] == "transmitting" for event in result["trace_events"])
    assert any(event["kind"] == "hop_arrival" for event in result["trace_events"])
    assert all(packet["route_history"][0] == "Main Gate" for packet in result["packets"])


def test_packet_transfer_per_packet_drop_and_duplicate_are_not_crypto_checks():
    initial_route = compute_route(demo_graph(), "dijkstra", "Main Gate", "Data Center")["path"]
    midpoint_edge_index = max(0, (len(initial_route) - 2) // 2)
    expected_loss_edge = (initial_route[midpoint_edge_index], initial_route[midpoint_edge_index + 1])
    payload = base_payload(packet_profiles=[
        {"packet_type": "data", "size_bytes": 512, "payload": "one", "scenario": "drop"},
        {"packet_type": "ack", "size_bytes": 64, "payload": "two", "scenario": "duplicate"},
    ])
    response = client.post("/packets/transfer", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    first, second = result["packets"]
    assert first["status"] == "dropped_simulated"
    # The configured loss is injected on a real route edge, not before dispatch.
    assert first["lost_on_edge"] is not None
    lost_edge = first["lost_on_edge"]
    assert (lost_edge["from_node"], lost_edge["to_node"]) == expected_loss_edge
    assert lost_edge["from_node"] in first["route_history"]
    assert first["attempted_hops"] == first["hops"] + 1
    assert first["edge_attempts"][-1]["status"] == "lost"
    assert first["edge_attempts"][-1]["from_node"] == lost_edge["from_node"]
    assert first["edge_attempts"][-1]["to_node"] == lost_edge["to_node"]
    assert second["status"] == "delivered" and second["duplicate_copies"] == 1
    assert result["metrics"]["dropped_simulated"] == 1
    assert result["metrics"]["duplicate_copies"] == 1
    packet_events = [event for event in result["trace_events"] if event["packet_id"] == first["packet_id"]]
    loss_event = next(event for event in packet_events if event["kind"] == "packet_lost_on_link")
    assert loss_event["from_node"] == lost_edge["from_node"]
    assert loss_event["to_node"] == lost_edge["to_node"]
    assert any(event["kind"] == "transmitting" for event in packet_events)
    assert any(event["kind"] == "serialization_complete" for event in packet_events)
    assert packet_events.index(loss_event) > max(
        i for i, event in enumerate(packet_events)
        if event["kind"] == "serialization_complete"
        and event["from_node"] == lost_edge["from_node"]
        and event["to_node"] == lost_edge["to_node"]
    )
    assert not any("signature" in event["message"].lower() for event in result["trace_events"])


def test_configured_link_loss_probability_is_observed_after_transmission():
    graph = demo_graph()
    path = compute_route(graph, "dijkstra", "Main Gate", "Data Center")["path"]
    u, v = path[0], path[1]
    props = graph.get_edge_properties(u, v)
    graph.set_edge_properties(u, v, **{**props, "loss_probability": 1.0})
    STATE.replace_graph(graph)

    response = client.post("/packets/transfer", json=base_payload(packet_profiles=[
        {"packet_type": "data", "size_bytes": 512, "payload": "probabilistic link loss", "scenario": "normal"}
    ]))
    assert response.status_code == 200, response.text
    result = response.json()
    packet = result["packets"][0]
    assert packet["status"] == "dropped_link_loss"
    assert packet["lost_on_edge"]["from_node"] == u
    assert packet["lost_on_edge"]["to_node"] == v
    kinds = [event["kind"] for event in result["trace_events"]]
    assert "transmitting" in kinds
    assert "serialization_complete" in kinds
    assert "packet_lost_on_link" in kinds
    assert kinds.index("packet_lost_on_link") > kinds.index("serialization_complete")


def test_packet_transfer_static_and_dynamic_routing_react_differently_to_failure():
    graph = demo_graph()
    route = compute_route(graph, "dijkstra", "Main Gate", "Data Center")["path"]
    u, v = route[0], route[1]
    common = base_payload(
        packet_profiles=[{"packet_type": "data", "size_bytes": 512, "payload": "failure test", "scenario": "normal"}],
        duration_ms=1000,
        failures=[{"kind": "link", "u": u, "v": v, "at_ms": 0, "duration_ms": 500}],
    )
    static_response = client.post("/packets/transfer", json={**common, "algorithm": "dijkstra_static"})
    dynamic_response = client.post("/packets/transfer", json={**common, "algorithm": "dijkstra_dynamic"})
    assert static_response.status_code == 200, static_response.text
    assert dynamic_response.status_code == 200, dynamic_response.text
    static_packet = static_response.json()["packets"][0]
    dynamic_packet = dynamic_response.json()["packets"][0]
    assert static_packet["status"] == "dropped_link_failure"
    assert dynamic_packet["status"] == "delivered"
    assert any(e["kind"] == "route_recalculated" for e in dynamic_response.json()["trace_events"])


def test_packet_transfer_validates_types_counts_and_nodes():
    bad_type = base_payload(packet_profiles=[{"packet_type": "unknown", "size_bytes": 10, "scenario": "normal"}])
    assert client.post("/packets/transfer", json=bad_type).status_code == 422
    bad_size = base_payload(packet_profiles=[{"packet_type": "data", "size_bytes": 0, "scenario": "normal"}])
    assert client.post("/packets/transfer", json=bad_size).status_code == 422
    bad_nodes = base_payload(source="Missing Node")
    assert client.post("/packets/transfer", json=bad_nodes).status_code == 422


def test_packet_transfer_reports_payload_and_route_metadata_tampering_as_delivered_faults():
    payload = base_payload(packet_profiles=[
        {"packet_type": "data", "size_bytes": 512, "payload": "original payload", "scenario": "tamper_payload"},
        {"packet_type": "control", "size_bytes": 128, "payload": "control header", "scenario": "tamper_route"},
    ])
    response = client.post("/packets/transfer", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    first, second = result["packets"]
    assert first["status"] == "delivered_payload_modified"
    assert first["payload_modified"] is True
    assert second["status"] == "delivered_route_header_modified"
    assert second["route_header_modified"] is True
    assert result["metrics"]["payload_tampered_packets"] == 1
    assert result["metrics"]["route_header_tampered_packets"] == 1
    assert result["metrics"]["packet_delivery_ratio"] == 1.0
    assert any(event["kind"] == "payload_tampered" for event in result["trace_events"])
    assert any(event["kind"] == "route_header_tampered" for event in result["trace_events"])
