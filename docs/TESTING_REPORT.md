# Testing Report

## Backend

The backend test suite is run with:

```bash
cd backend
python -m pytest -q
```

The current delivered source has **67 passing backend tests** in the preparation environment. Python source and test compilation also pass. Tests cover the legacy graph/algorithm/math/token features and the added research implementation, including:

- Graph import/export and independent routing-cost/propagation-delay fields.
- Graph CRUD and validation.
- Structural and operational graph analysis.
- BFS/DFS/Dijkstra route behavior.
- Static versus dynamic Dijkstra under a link failure.
- Dynamic route recovery under node failure.
- Queue overflow and TTL classification.
- Deterministic logical simulation with a fixed seed.
- Ed25519 signature, payload integrity and replay checks.
- Security rejection separated from network delivery.
- Exact Student-t critical-value checks.
- Paired comparison matching by repetition and seed.
- Generated topology connectivity and deterministic generation.
- API packet-transfer workflow, mixed packet-class profiles, per-packet in-flight loss on a named route edge, seeded link-loss probability after serialization, duplicate and tampering scenarios, static-versus-dynamic failure response, experiment persistence and paginated packet-outcome retrieval.
- Invalid failure schedule responses and configured backend port.

## Frontend

The intended commands are:

```bash
cd frontend
npm install
npm test
npm run build
```

**TypeScript check:** `tsc --noEmit` passed using the environment global TypeScript 5.8.3. The Vitest run could not start because the reused original ZIP contains macOS-specific optional native dependencies and the Linux `rolldown` binding is absent. The Vite production build is therefore not verified in this environment. On the receiving Mac, run `npm ci`, then `npm test` and `npm run build` to verify using locally installed platform dependencies. No frontend test/build success is claimed. On the receiving Mac, use Node 24.x and run the commands above.

## Integration

The backend API was exercised through FastAPI's `TestClient` for health, packet-transfer creation and event traces, packet profile validation, static/dynamic routing under failure, experiment creation, saved experiment listing/detail retrieval, invalid failure rejection and graph operational analysis. A full browser-driven frontend/backend end-to-end session was not available during this packaging run.

## Verification limitations

- Test results are from this container's Python environment, not the user's Mac.
- Wall-clock cryptographic performance is not deterministic.
- Passing tests do not establish external validity of the network model.
