"""Number theory (Unit 5): hand-written GCD, Extended Euclid, modular inverse/exponentiation, toy RSA.

ACADEMIC / TOY CRYPTOGRAPHY - NOT PRODUCTION SECURITY.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

TOY_WARNING = "Academic/toy cryptography - small keys, no padding. NOT production security. Never use it for real secrets."


class NumberTheoryError(ValueError):
    def __init__(self, message: str, code: str = "invalid_input", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def gcd(a: int, b: int) -> int:
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


def gcd_steps(a: int, b: int) -> list[dict[str, int]]:
    steps = []
    x, y = abs(a), abs(b)
    while y:
        steps.append({"a": x, "b": y, "q": x // y, "r": x % y})
        x, y = y, x % y
    return steps


def ext_gcd(a: int, b: int) -> tuple[int, int, int]:
    """Return (g, x, y) with a*x + b*y = g = gcd(a, b) (Bezout identity), g >= 0."""
    old_r, r, old_s, s, old_t, t = a, b, 1, 0, 0, 1
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    if old_r < 0:
        old_r, old_s, old_t = -old_r, -old_s, -old_t
    return old_r, old_s, old_t


def ext_gcd_steps(a: int, b: int) -> list[dict[str, int]]:
    rows = []
    old_r, r, old_s, s, old_t, t = a, b, 1, 0, 0, 1
    rows.append({"q": 0, "r": old_r, "s": old_s, "t": old_t})
    rows.append({"q": 0, "r": r, "s": s, "t": t})
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
        rows.append({"q": q, "r": r, "s": s, "t": t})
    return rows


def mod_inverse(a: int, m: int) -> int:
    if m <= 1:
        raise NumberTheoryError("Modulus must be greater than 1.", "invalid_modulus")
    g, x, _ = ext_gcd(a % m, m)
    if g != 1:
        raise NumberTheoryError(f"No modular inverse: gcd({a}, {m}) = {g} (operands are not coprime).", "not_coprime")
    return x % m


def mod_exp(base: int, exp: int, mod: int) -> int:
    """Square-and-multiply."""
    if mod < 1:
        raise NumberTheoryError("Modulus must be at least 1.", "invalid_modulus")
    if exp < 0:
        raise NumberTheoryError("Exponent must be non-negative.", "invalid_exponent")
    result, b, e = 1 % mod, base % mod, exp
    while e:
        if e & 1:
            result = (result * b) % mod
        b = (b * b) % mod
        e >>= 1
    return result


_SMALL_PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]


def is_probable_prime(n: int, rounds: int = 16) -> bool:
    """Miller-Rabin. Deterministic for n < 3.3e24 with the fixed bases; extra random bases beyond that."""
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n == p:
            return True
        if n % p == 0:
            return False
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    bases = list(_SMALL_PRIMES)
    if n >= 3_317_044_064_679_887_385_961_981:
        bases += [2 + secrets.randbelow(n - 3) for _ in range(rounds)]
    for a in bases:
        x = mod_exp(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = (x * x) % n
            if x == n - 1:
                break
        else:
            return False
    return True


def generate_prime(bits: int) -> int:
    if bits < 8 or bits > 256:
        raise NumberTheoryError("Prime size must be between 8 and 256 bits (toy range).", "invalid_bits")
    while True:
        c = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if is_probable_prime(c):
            return c


@dataclass
class RSAKeyPair:
    p: int
    q: int
    n: int
    phi: int
    e: int
    d: int

    def public(self) -> dict[str, int]:
        return {"n": self.n, "e": self.e}

    def private(self) -> dict[str, int]:
        return {"n": self.n, "d": self.d}

    def steps(self) -> list[str]:
        return [
            f"p = {self.p}, q = {self.q} (probable primes)",
            f"n = p x q = {self.n}",
            f"phi(n) = (p-1)(q-1) = {self.phi}",
            f"e = {self.e}, gcd(e, phi) = {gcd(self.e, self.phi)} (must be 1)",
            f"d = e^-1 mod phi = {self.d}",
            f"check: e x d mod phi = {(self.e * self.d) % self.phi}",
        ]


def keypair_from_primes(p: int, q: int, e: int = 65537) -> RSAKeyPair:
    if p == q:
        raise NumberTheoryError("p and q must be distinct.", "invalid_primes")
    if not (is_probable_prime(p) and is_probable_prime(q)):
        raise NumberTheoryError("p and q must both be prime.", "invalid_primes")
    phi = (p - 1) * (q - 1)
    if e <= 1 or e >= phi or gcd(e, phi) != 1:
        raise NumberTheoryError("Public exponent e must satisfy 1 < e < phi and gcd(e, phi) = 1.", "invalid_exponent")
    return RSAKeyPair(p, q, p * q, phi, e, mod_inverse(e, phi))


def generate_keypair(bits: int = 48, e: int = 65537) -> RSAKeyPair:
    while True:
        p, q = generate_prime(bits), generate_prime(bits)
        if p == q:
            continue
        phi = (p - 1) * (q - 1)
        if gcd(e, phi) == 1:
            return keypair_from_primes(p, q, e)


def encrypt_int(m: int, n: int, e: int) -> int:
    if n <= 1:
        raise NumberTheoryError("Modulus n must be greater than 1.", "invalid_modulus")
    if not 0 <= m < n:
        raise NumberTheoryError(f"Message integer must satisfy 0 <= m < n ({n}).", "message_out_of_range")
    return mod_exp(m, e, n)


def decrypt_int(c: int, n: int, d: int) -> int:
    if n <= 1:
        raise NumberTheoryError("Modulus n must be greater than 1.", "invalid_modulus")
    if not 0 <= c < n:
        raise NumberTheoryError(f"Ciphertext must satisfy 0 <= c < n ({n}).", "message_out_of_range")
    return mod_exp(c, d, n)
