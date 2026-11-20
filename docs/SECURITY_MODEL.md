# Security Model

## Implemented mechanism

The research security module uses the `cryptography` library's Ed25519 implementation and SHA-256.

A signed packet envelope includes:

- Packet identifier.
- Source and destination identifiers.
- SHA-256 digest of the payload.
- Simulation generation time.
- Expiry time.
- Nonce.

The envelope is serialized as canonical JSON (sorted keys and compact separators) and signed with an Ed25519 private key. The verifier checks the signature, recalculated payload digest, expiry and nonce freshness.

## Security properties demonstrated

- **Authenticity:** signature verification can establish that the canonical envelope was signed by the holder of the corresponding private key, assuming the public key is trusted.
- **Integrity:** the payload digest binds the payload to the signed envelope.
- **Expiry:** packets that arrive after their configured expiry are rejected.
- **Replay detection:** a nonce already seen in the current simulation run is rejected.

The former standalone Packet Security demo has been replaced in the main navigation by the interactive Packet Transfer simulation. Packet Transfer includes payload and route-metadata fault injection without claiming cryptographic verification.

## Packet security in experiments

When enabled, every generated simulation packet is signed and verified when it reaches the destination. Optional payload tampering can cause digest verification failure. Optional duplicate/replay injection reuses a signed packet nonce and is rejected by the run-local replay cache.

Network delivery and security acceptance are recorded separately. This prevents authentication failures from being incorrectly described as link loss.

## Explicit limitations

- Packet payloads are **not encrypted**; confidentiality is not provided.
- Keys are ephemeral for each demonstration/experiment run. Persistent identity, rotation, revocation, certificate trust, secure key storage and multi-user key distribution are not implemented.
- The replay cache is scoped to a single experiment run and is not durable across process restarts.
- Signing and verification latency are local wall-clock timings and are environment-dependent.
- The project is not a production security product.
- The older classroom RSA/token endpoints are retained as educational compatibility features. They must not be treated as the actual packet authentication mechanism.
