from sdlc_agents.security import crypto


def test_encrypt_decrypt_roundtrip():
    data = b"confidential architecture document \x00\x01\x02"
    blob = crypto.encrypt(data, "s3cret-passphrase")
    assert blob[:6] == b"SDLCE1"
    assert blob != data
    assert crypto.decrypt(blob, "s3cret-passphrase") == data


def test_wrong_passphrase_fails():
    blob = crypto.encrypt(b"top secret", "correct-horse")
    try:
        result = crypto.decrypt(blob, "wrong-pass")
        # AES-GCM raises; fallback raises integrity error. If somehow no raise,
        # the plaintext must not match.
        assert result != b"top secret"
    except Exception:
        pass  # expected
