# Algorithms and Security — Research Edition

The primary routing comparison is BFS (minimum-hop baseline), Static Dijkstra (frozen destination-specific time-zero forwarding entries) and Dynamic Dijkstra (recalculation after supported topology changes). DFS remains a traversal demonstration in Network Studio / Routing & Resilience and is not a shortest-path method.

Routing cost (`weight`) and propagation delay (`propagation_delay_ms`) are independent link attributes. Dijkstra minimizes routing cost; the event simulator adds propagation delay after serialization.

Packet authentication in the research module uses Ed25519 signatures and SHA-256 over a canonical packet envelope. The envelope includes packet ID, source, destination, payload digest, generation time, expiry and nonce. Replay validation is scoped to one experiment run.

Ed25519/SHA-256 remains an optional experiment capability for measuring authentication overhead; it is not a standalone static application page. It provides authenticity and integrity only and does not encrypt packet payloads or provide confidentiality. The Packet Transfer page separately visualizes mixed traffic and fault-injection scenarios without claiming cryptographic validation. The legacy classroom RSA/token endpoints are educational compatibility features, not the research security mechanism.

See `ALGORITHM_DOCUMENTATION.md`, `SECURITY_MODEL.md`, `SIMULATION_MODEL.md` and `EXPERIMENTAL_METHODOLOGY.md` for implementation details and limitations.
