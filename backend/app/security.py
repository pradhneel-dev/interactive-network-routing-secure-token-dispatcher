"""Token dispatcher security layer: digest + toy-RSA signature + encrypted nonce.

ACADEMIC / TOY CRYPTOGRAPHY - NOT PRODUCTION SECURITY.
Concepts kept distinct:
  * digest    - SHA-256 of the payload, detects payload modification
  * signature - toy-RSA signature over canonical signed metadata, detects altered signed fields
  * nonce     - random value encrypted with the recipient public key (confidentiality demo)
  * loss      - detected separately by comparing expected vs received packet IDs (see packets.py)
"""
from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from . import numtheory as nt

KEY_BITS = 48  # each prime; n is about 96 bits. Demonstration size only.


class KeyRegistry:
    """Associates a toy key pair with each node (generated lazily)."""

    def __init__(self, bits: int = KEY_BITS) -> None:
        self.bits = bits
        self.keys: dict[str, nt.RSAKeyPair] = {}

    def ensure(self, node: str) -> nt.RSAKeyPair:
        if node not in self.keys:
            self.keys[node] = nt.generate_keypair(self.bits)
        return self.keys[node]

    def reset(self) -> None:
        self.keys.clear()


def digest_payload(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_metadata(packet_id: str, seq: int, source: str, destination: str, route: list[str],
                       payload_digest: str, nonce: int) -> str:
    """Deterministic string of every signed field."""
    return json.dumps(
        {"packet_id": packet_id, "seq": seq, "source": source, "destination": destination,
         "route": list(route), "payload_digest": payload_digest, "nonce": nonce},
        sort_keys=True, separators=(",", ":"),
    )


def _hash_to_int(canonical: str, n: int) -> int:
    # Reduced mod n because the toy modulus is smaller than a SHA-256 value (another toy simplification).
    return int(hashlib.sha256(canonical.encode("utf-8")).hexdigest(), 16) % n


def sign(canonical: str, key: nt.RSAKeyPair) -> int:
    return nt.mod_exp(_hash_to_int(canonical, key.n), key.d, key.n)


def verify_signature(canonical: str, signature: int, n: int, e: int) -> bool:
    if not isinstance(signature, int) or not 0 <= signature < n:
        return False
    return nt.mod_exp(signature, e, n) == _hash_to_int(canonical, n)


def create_token(registry: KeyRegistry, packet_id: str, seq: int, source: str, destination: str,
                 route: list[str], payload: str) -> dict[str, Any]:
    sender, recipient = registry.ensure(source), registry.ensure(destination)
    nonce_bits = min(64, recipient.n.bit_length() - 2)
    nonce = 2 + secrets.randbelow((1 << nonce_bits) - 2)
    enc_nonce = nt.encrypt_int(nonce, recipient.n, recipient.e)
    pd = digest_payload(payload)
    canonical = canonical_metadata(packet_id, seq, source, destination, route, pd, nonce)
    return {
        "token_id": f"TOK-{packet_id}", "packet_id": packet_id, "seq": seq, "source": source,
        "destination": destination, "route": list(route), "payload_digest": pd,
        "encrypted_nonce": enc_nonce, "signature": sign(canonical, sender),
    }


def verify_token(registry: KeyRegistry, token: dict[str, Any], payload: str,
                 packet_header: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run every check separately; valid only if ALL pass.

    token: the signed artifact as received.
    packet_header: the packet's own (unsigned-in-transit) id/seq/source/destination/route as received.
    """
    reasons: list[str] = []
    checks: dict[str, Any] = {}
    sender, recipient = registry.ensure(token["source"]), registry.ensure(token["destination"])

    # 1. nonce recovery with the recipient's private key
    try:
        nonce = nt.decrypt_int(token["encrypted_nonce"], recipient.n, recipient.d)
        checks["nonce_recovered"] = nonce
    except nt.NumberTheoryError:
        nonce = None
        checks["nonce_recovered"] = None
        reasons.append("Encrypted nonce could not be decrypted (out of range).")

    # 2. signature over the token's own signed fields
    if nonce is None:
        sig_ok = False
    else:
        canon = canonical_metadata(token["packet_id"], token["seq"], token["source"], token["destination"],
                                   token["route"], token["payload_digest"], nonce)
        sig_ok = verify_signature(canon, token["signature"], sender.n, sender.e)
    checks["signature_valid"] = sig_ok
    if not sig_ok:
        reasons.append("Signature does not match the token's signed metadata (token altered or forged).")

    # 3. signature against the packet header actually received (route/ID/destination tampering)
    header_ok = True
    if packet_header is not None and nonce is not None:
        canon_pkt = canonical_metadata(packet_header["packet_id"], packet_header["seq"], packet_header["source"],
                                       packet_header["destination"], packet_header["route"],
                                       token["payload_digest"], nonce)
        header_ok = verify_signature(canon_pkt, token["signature"], sender.n, sender.e)
        if not header_ok:
            diffs = [k for k in ("packet_id", "seq", "source", "destination", "route")
                     if packet_header[k] != token[k]]
            reasons.append("Signed metadata of the received packet differs from what was signed"
                           + (f" (changed: {', '.join(diffs)})." if diffs else "."))
    checks["metadata_signature_valid"] = header_ok

    # 4. payload digest recomputed from the received payload
    digest_ok = digest_payload(payload) == token["payload_digest"]
    checks["digest_matches"] = digest_ok
    if not digest_ok:
        reasons.append("Recomputed payload digest differs from the signed digest (payload modified).")

    if not sig_ok:
        status = "Signature Invalid"
    elif not header_ok:
        status = "Metadata Tampered"
    elif not digest_ok:
        status = "Payload Modified"
    else:
        status = "Delivered & Verified"
    valid = sig_ok and header_ok and digest_ok
    return {"valid": valid, "status": status, "checks": checks,
            "reasons": reasons or ["All checks passed: nonce recovered, signature valid, metadata and payload digest match."]}
