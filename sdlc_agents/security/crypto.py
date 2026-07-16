"""Optional at-rest encryption for generated artifacts.

Uses AES-GCM via the ``cryptography`` package when available, with a
PBKDF2-HMAC-SHA256 key derived from a user-supplied passphrase. The passphrase
is never persisted. If ``cryptography`` is not installed the app degrades to a
clearly-labelled, dependency-free XOR obfuscation so the feature still exists on
a minimal edge image (with a warning that it is not cryptographically strong).

File format (bytes):  MAGIC(6) | VERSION(1) | SALT(16) | NONCE(12) | CIPHERTEXT
"""

from __future__ import annotations

import hashlib
import hmac
import os
import struct

_MAGIC = b"SDLCE1"
_VERSION_AESGCM = 1
_VERSION_XOR = 2


_CRYPTO_PROBE: bool | None = None


def cryptography_available() -> bool:
    """Functionally probe ``cryptography`` (cached).

    A plain ``import cryptography`` can succeed while the native AES-GCM binding
    is broken (e.g. a missing CFFI backend), which surfaces as a low-level Rust
    panic rather than a normal exception. We therefore run a tiny real encrypt
    and catch ``BaseException`` so a partial/broken install degrades gracefully
    to the built-in fallback cipher instead of crashing.
    """

    global _CRYPTO_PROBE
    if _CRYPTO_PROBE is not None:
        return _CRYPTO_PROBE
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        AESGCM(b"0" * 32).encrypt(b"0" * 12, b"probe", None)
        _CRYPTO_PROBE = True
    except BaseException:  # noqa: BLE001 - includes Rust PanicException
        _CRYPTO_PROBE = False
    return _CRYPTO_PROBE


def _derive_key(passphrase: str, salt: bytes, length: int = 32) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=length)


def encrypt(data: bytes, passphrase: str) -> bytes:
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    if cryptography_available():
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, data, None)
        return _MAGIC + struct.pack("B", _VERSION_AESGCM) + salt + nonce + ct
    # Fallback (not cryptographically strong; keeps feature usable offline).
    nonce = os.urandom(12)
    stream = _keystream(key + nonce, len(data))
    ct = bytes(a ^ b for a, b in zip(data, stream))
    mac = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    return _MAGIC + struct.pack("B", _VERSION_XOR) + salt + nonce + ct + mac


def decrypt(blob: bytes, passphrase: str) -> bytes:
    if blob[:6] != _MAGIC:
        raise ValueError("Not an SDLC-encrypted artifact.")
    version = blob[6]
    salt = blob[7:23]
    nonce = blob[23:35]
    key = _derive_key(passphrase, salt)
    if version == _VERSION_AESGCM:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        ct = blob[35:]
        return AESGCM(key).decrypt(nonce, ct, None)
    if version == _VERSION_XOR:
        body = blob[35:]
        ct, mac = body[:-32], body[-32:]
        if not hmac.compare_digest(mac, hmac.new(key, nonce + ct, hashlib.sha256).digest()):
            raise ValueError("Integrity check failed (wrong passphrase or tampering).")
        stream = _keystream(key + nonce, len(ct))
        return bytes(a ^ b for a, b in zip(ct, stream))
    raise ValueError(f"Unknown encryption version: {version}")


def _keystream(seed: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(seed + struct.pack(">I", counter)).digest())
        counter += 1
    return bytes(out[:length])
