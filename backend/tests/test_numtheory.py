import math, pytest
from app import numtheory as nt


def test_gcd_and_bezout():
    assert nt.gcd(48, 18) == 6 and nt.gcd(0, 5) == 5 and nt.gcd(-12, 18) == 6
    for a, b in [(240, 46), (17, 5), (-35, 15), (0, 7), (99, 78)]:
        g, x, y = nt.ext_gcd(a, b)
        assert a * x + b * y == g == math.gcd(a, b)


def test_modular_inverse():
    assert nt.mod_inverse(3, 11) == 4
    for a in range(1, 26):
        if math.gcd(a, 26) == 1:
            assert (a * nt.mod_inverse(a, 26)) % 26 == 1
    with pytest.raises(nt.NumberTheoryError) as e: nt.mod_inverse(6, 9)
    assert e.value.code == "not_coprime"
    with pytest.raises(nt.NumberTheoryError): nt.mod_inverse(3, 1)


def test_mod_exp_matches_pow():
    for b, e, m in [(2, 10, 1000), (7, 0, 13), (123456789, 987654321, 1000000007), (5, 3, 1)]:
        assert nt.mod_exp(b, e, m) == pow(b, e, m)
    with pytest.raises(nt.NumberTheoryError): nt.mod_exp(2, -1, 5)


def test_primes():
    assert [n for n in range(2, 30) if nt.is_probable_prime(n)] == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    assert not nt.is_probable_prime(561) and nt.is_probable_prime(2**61 - 1)
    p = nt.generate_prime(32); assert nt.is_probable_prime(p) and p.bit_length() == 32


def test_rsa_roundtrip():
    kp = nt.generate_keypair(32)
    assert kp.n == kp.p * kp.q and kp.phi == (kp.p - 1) * (kp.q - 1)
    assert math.gcd(kp.e, kp.phi) == 1 and (kp.e * kp.d) % kp.phi == 1
    for m in (0, 1, 42, kp.n - 1):
        assert nt.decrypt_int(nt.encrypt_int(m, kp.n, kp.e), kp.n, kp.d) == m
    with pytest.raises(nt.NumberTheoryError): nt.encrypt_int(kp.n, kp.n, kp.e)
    small = nt.keypair_from_primes(61, 53, 17)
    assert small.n == 3233 and small.d == 2753
    with pytest.raises(nt.NumberTheoryError): nt.keypair_from_primes(61, 61)
    with pytest.raises(nt.NumberTheoryError): nt.keypair_from_primes(60, 53)
