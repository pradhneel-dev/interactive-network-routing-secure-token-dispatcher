"""Ed25519 packet-authentication primitives for the local IRSD simulator.

This module provides authenticity/integrity only. It does not encrypt packet payloads.
Private keys are ephemeral per process/run in this educational single-user application.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(payload: bytes | str) -> str:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hashlib.sha256(raw).hexdigest()


@dataclass
class Ed25519Identity:
    private_key: Ed25519PrivateKey

    @classmethod
    def generate(cls) -> "Ed25519Identity":
        return cls(Ed25519PrivateKey.generate())

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self.private_key.public_key()

    def public_key_b64(self) -> str:
        raw = self.public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return base64.b64encode(raw).decode("ascii")

    def sign(self, message: bytes) -> tuple[str, float]:
        start = time.perf_counter_ns()
        signature = self.private_key.sign(message)
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        return base64.b64encode(signature).decode("ascii"), elapsed_ms

    @staticmethod
    def verify(public_key_b64: str, signature_b64: str, message: bytes) -> tuple[bool, float]:
        start = time.perf_counter_ns()
        try:
            public = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64, validate=True))
            signature = base64.b64decode(signature_b64, validate=True)
            public.verify(signature, message)
            ok = True
        except (ValueError, TypeError, InvalidSignature):
            ok = False
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        return ok, elapsed_ms


def build_packet_envelope(packet_id: str, source: str, destination: str, payload: str,
                          generated_at_ms: float, expires_at_ms: float | None, nonce: str) -> dict[str, Any]:
    return {
        "packet_id": packet_id,
        "source": source,
        "destination": destination,
        "payload_sha256": sha256_hex(payload),
        "generated_at_ms": round(generated_at_ms, 6),
        "expires_at_ms": None if expires_at_ms is None else round(expires_at_ms, 6),
        "nonce": nonce,
    }


def create_signed_packet(identity: Ed25519Identity, packet_id: str, source: str, destination: str,
                         payload: str, generated_at_ms: float, expires_at_ms: float | None,
                         nonce: str | None = None) -> dict[str, Any]:
    nonce_value = nonce or secrets.token_urlsafe(18)
    envelope = build_packet_envelope(packet_id, source, destination, payload,
                                     generated_at_ms, expires_at_ms, nonce_value)
    signature, sign_ms = identity.sign(canonical_json(envelope))
    return {
        "envelope": envelope,
        "signature": signature,
        "public_key": identity.public_key_b64(),
        "signing_time_ms": sign_ms,
    }


def verify_signed_packet(signed: dict[str, Any], payload: str, *, arrival_at_ms: float,
                         seen_nonces: set[str]) -> dict[str, Any]:
    envelope = signed.get("envelope") if isinstance(signed, dict) else None
    if not isinstance(envelope, dict):
        return {"valid": False, "status": "invalid_envelope", "reason": "Signed envelope is missing or malformed.", "verification_time_ms": 0.0}
    digest_ok = sha256_hex(payload) == envelope.get("payload_sha256")
    expiry = envelope.get("expires_at_ms")
    not_expired = expiry is None or arrival_at_ms <= float(expiry)
    nonce = str(envelope.get("nonce", ""))
    not_replayed = bool(nonce) and nonce not in seen_nonces
    if nonce:
        seen_nonces.add(nonce)
    signature_ok, verify_ms = Ed25519Identity.verify(
        str(signed.get("public_key", "")), str(signed.get("signature", "")), canonical_json(envelope)
    )
    # Signature validity, payload integrity, expiry and replay are independent checks.
    checks = {
        "signature_valid": signature_ok,
        "payload_digest_matches": digest_ok,
        "not_expired": not_expired,
        "nonce_not_replayed": not_replayed,
    }
    valid = all(checks.values())
    if not signature_ok:
        status, reason = "invalid_signature", "Ed25519 signature verification failed."
    elif not digest_ok:
        status, reason = "payload_tampered", "Payload SHA-256 digest does not match the signed envelope."
    elif not not_expired:
        status, reason = "expired", "Packet arrived after its signed expiry time."
    elif not not_replayed:
        status, reason = "replay_rejected", "Packet nonce has already been seen."
    else:
        status, reason = "authenticated", "Signature, payload digest, expiry and replay checks passed."
    return {"valid": valid, "status": status, "reason": reason,
            "checks": checks, "verification_time_ms": verify_ms}
