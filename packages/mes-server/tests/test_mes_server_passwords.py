from mes_server.auth.passwords import hash_password, verify_password


def test_hash_does_not_contain_the_password():
    assert "secret123" not in hash_password("secret123")


def test_hash_uses_argon2id():
    assert hash_password("secret123").startswith("$argon2id$")


def test_same_password_produces_different_hashes():
    assert hash_password("secret123") != hash_password("secret123")


def test_correct_password_is_accepted():
    valid, new_hash = verify_password("secret123", hash_password("secret123"))
    assert valid
    assert new_hash is None


def test_wrong_password_is_rejected():
    valid, _ = verify_password("wrong-password", hash_password("secret123"))
    assert not valid
