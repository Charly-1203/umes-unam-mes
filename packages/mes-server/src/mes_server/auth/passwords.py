"""Password hashing.

Passwords are hashed with Argon2id, the algorithm recommended by OWASP. Only the hash is
stored; it embeds the algorithm and its parameters, so they can be strengthened later and
existing hashes are upgraded the next time each user signs in.
"""

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()

MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    """Hash a password for storage.

    Args:
        password: Clear-text password.

    Returns:
        The encoded hash, including algorithm, parameters and salt.
    """
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Check a password against a stored hash.

    Args:
        password: Clear-text password typed by the user.
        password_hash: Hash stored for the user.

    Returns:
        A pair ``(valid, new_hash)``. ``new_hash`` is set when the password is valid but the
        stored hash uses outdated parameters and should be replaced.
    """
    return _hasher.verify_and_update(password, password_hash)


# Verifying against this hash when a username does not exist makes failed sign-ins take the
# same time whether or not the user exists, so response times do not reveal valid usernames.
DUMMY_HASH = hash_password("dummy-password-for-timing")
