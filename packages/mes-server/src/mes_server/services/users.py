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
from mes_server.db.models import DowntimeEvent, ExecutionRecord, User
from mes_server.services import catalog
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
            "starting with a letter or digit.",
            code="username_format",
            field="username",
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
        raise ValidationError(
            f"Password must have at least {MIN_PASSWORD_LENGTH} characters.",
            code="password_too_short",
            field="password",
        )


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
        raise ValidationError("Full name must not be blank.", code="blank", field="full_name")
    if get_user_by_username(session, normalized) is not None:
        raise AlreadyExistsError(f"User '{normalized}' already exists.", field="username")

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


# ---------------------------------------------------------------------------------------------
# Administration
# ---------------------------------------------------------------------------------------------
REFERENCES = (
    catalog.Reference("execution records", ExecutionRecord.operator_id),
    catalog.Reference("downtime events", DowntimeEvent.reported_by_id),
)
"""Records that point at a user and therefore keep it from being deleted."""


def get_user(session: Session, user_id: int) -> User:
    """Load a user.

    Args:
        session: Open database session.
        user_id: Primary key.

    Returns:
        The user.

    Raises:
        NotFoundError: If it does not exist.
    """
    return catalog.get_or_raise(session, User, user_id)


def _is_last_active_admin(session: Session, user: User) -> bool:
    return user.role == Role.ADMIN and user.is_active and count_active_admins(session) <= 1


def _ensure_not_self(user_id: int, actor_id: int, message: str) -> None:
    if user_id == actor_id:
        raise ValidationError(message, code="self_action")


def update_user(
    session: Session, user_id: int, *, full_name: str, role: Role, actor_id: int
) -> User:
    """Change a user's name and role.

    Args:
        session: Open database session. The caller commits.
        user_id: User to change.
        full_name: New name shown on screens.
        role: New role.
        actor_id: Id of the administrator making the change.

    Returns:
        The updated user.

    Raises:
        NotFoundError: If the user does not exist.
        ValidationError: If the name is blank, the administrator changes their own role, or
            the change would leave no active administrator.
    """
    user = get_user(session, user_id)
    new_role = Role(role)
    if new_role != user.role:
        _ensure_not_self(user_id, actor_id, "You cannot change your own role.")
        if _is_last_active_admin(session, user):
            raise ValidationError(
                "At least one active administrator is required.", code="last_admin"
            )
    if not full_name.strip():
        raise ValidationError("Full name must not be blank.", code="blank", field="full_name")
    user.full_name = full_name.strip()
    user.role = new_role
    session.add(user)
    return user


def set_user_active(session: Session, user_id: int, active: bool, *, actor_id: int) -> User:
    """Activate or deactivate a user. Inactive users cannot sign in.

    Args:
        session: Open database session. The caller commits.
        user_id: User to change.
        active: New state.
        actor_id: Id of the administrator making the change.

    Returns:
        The user.

    Raises:
        NotFoundError: If the user does not exist.
        ValidationError: If administrators deactivate themselves or the last active
            administrator.
    """
    user = get_user(session, user_id)
    if not active:
        _ensure_not_self(user_id, actor_id, "You cannot deactivate yourself.")
        if _is_last_active_admin(session, user):
            raise ValidationError(
                "At least one active administrator is required.", code="last_admin"
            )
    user.is_active = active
    session.add(user)
    return user


def set_password(session: Session, user_id: int, password: str) -> User:
    """Replace a user's password.

    Args:
        session: Open database session. The caller commits.
        user_id: User to change.
        password: New clear-text password; only its hash is stored.

    Returns:
        The user.

    Raises:
        NotFoundError: If the user does not exist.
        ValidationError: If the password is too short.
    """
    user = get_user(session, user_id)
    validate_password(password)
    user.password_hash = hash_password(password)
    session.add(user)
    return user


def user_usage(session: Session, user_id: int) -> dict[str, int]:
    """Count the records that reference a user.

    Args:
        session: Open database session.
        user_id: Primary key.

    Returns:
        Non-zero counts keyed by reference label.
    """
    return catalog.count_references(session, user_id, REFERENCES)


def delete_user(session: Session, user_id: int, *, actor_role: Role, actor_id: int) -> None:
    """Delete a user without history.

    Args:
        session: Open database session. The caller commits.
        user_id: User to delete.
        actor_role: Role of who asks for the deletion.
        actor_id: Id of who asks for the deletion.

    Raises:
        NotFoundError: If the user does not exist.
        PermissionDeniedError: If the role is not an administrator.
        ValidationError: If administrators delete themselves or the last active administrator.
        InUseError: If executions or downtime events reference the user.
    """
    user = get_user(session, user_id)
    _ensure_not_self(user_id, actor_id, "You cannot delete yourself.")
    if _is_last_active_admin(session, user):
        raise ValidationError("At least one active administrator is required.", code="last_admin")
    catalog.delete_unused(session, user, user_id, REFERENCES, actor_role=actor_role)
