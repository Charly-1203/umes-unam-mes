"""User management and sign-in."""

import re

from sqlmodel import Session, func, select

from mes_core.enums import Role
from mes_server.auth.passwords import (
    DUMMY_HASH,
    MIN_PASSWORD_LENGTH,
    hash_password,
    verify_password,
)
from mes_server.db.models import User
from mes_server.services.errors import AlreadyExistsError, ValidationError

USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
"""3 to 64 characters: lowercase letters, digits, dot, underscore or hyphen."""


def normalize_username(username: str) -> str:
    """Return the canonical form of a username: trimmed and lowercase.

    Args:
        username: Username as typed.

    Returns:
        The normalized username.
    """
    return username.strip().lower()


def validate_username(username: str) -> str:
    """Normalize a username and check its format.

    Args:
        username: Username as typed.

    Returns:
        The normalized username.

    Raises:
        ValidationError: If the format is invalid.
    """
    normalized = normalize_username(username)
    if not USERNAME_PATTERN.match(normalized):
        raise ValidationError(
            "Username must be 3-64 characters: lowercase letters, digits, '.', '_' or '-', "
            "starting with a letter or digit."
        )
    return normalized


def validate_password(password: str) -> None:
    """Check that a password meets the minimum policy.

    Args:
        password: Clear-text password.

    Raises:
        ValidationError: If the password is too short or blank.
    """
    if len(password) < MIN_PASSWORD_LENGTH or not password.strip():
        raise ValidationError(f"Password must have at least {MIN_PASSWORD_LENGTH} characters.")


def get_user_by_username(session: Session, username: str) -> User | None:
    """Find a user by username, ignoring case and surrounding spaces.

    Args:
        session: Open database session.
        username: Username to look up.

    Returns:
        The user, or ``None`` if it does not exist.
    """
    statement = select(User).where(User.username == normalize_username(username))
    return session.exec(statement).first()


def create_user(
    session: Session,
    *,
    username: str,
    full_name: str,
    password: str,
    role: Role,
) -> User:
    """Create a user with a hashed password.

    Args:
        session: Open database session. The caller commits.
        username: Sign-in name; it is normalized to lowercase.
        full_name: Name shown on screens.
        password: Clear-text password; only its hash is stored.
        role: Permission level.

    Returns:
        The new user, already flushed so it has an ``id``.

    Raises:
        ValidationError: If any field breaks the rules.
        AlreadyExistsError: If the username is taken.
    """
    normalized = validate_username(username)
    validate_password(password)
    if not full_name.strip():
        raise ValidationError("Full name must not be blank.")
    if get_user_by_username(session, normalized) is not None:
        raise AlreadyExistsError(f"User '{normalized}' already exists.")

    user = User(
        username=normalized,
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        role=Role(role),
    )
    session.add(user)
    session.flush()
    return user


def authenticate(session: Session, username: str, password: str) -> User | None:
    """Check sign-in credentials.

    Inactive users cannot sign in. When the stored hash uses outdated parameters it is
    replaced transparently.

    Args:
        session: Open database session. The caller commits.
        username: Username as typed.
        password: Clear-text password as typed.

    Returns:
        The user when the credentials are valid, otherwise ``None``.
    """
    user = get_user_by_username(session, username)
    if user is None:
        verify_password(password, DUMMY_HASH)
        return None

    valid, new_hash = verify_password(password, user.password_hash)
    if not valid or not user.is_active:
        return None
    if new_hash is not None:
        user.password_hash = new_hash
        session.add(user)
    return user


def list_users(session: Session) -> list[User]:
    """Return every user ordered by username.

    Args:
        session: Open database session.

    Returns:
        The users.
    """
    return list(session.exec(select(User).order_by(User.username)).all())


def count_active_admins(session: Session) -> int:
    """Count active users with the administrator role.

    Args:
        session: Open database session.

    Returns:
        The number of active administrators.
    """
    statement = (
        select(func.count())
        .select_from(User)
        .where(User.role == Role.ADMIN, User.is_active == True)  # noqa: E712
    )
    return session.exec(statement).one()
