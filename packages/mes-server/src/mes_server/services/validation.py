"""Input normalization and validation shared by the services."""

import re

from mes_core.enums import Role
from mes_core.permissions import Permission, has_permission
from mes_server.services.errors import PermissionDeniedError, ValidationError

CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]*$")
"""Uppercase letters, digits, dot, underscore or hyphen, starting with a letter or digit."""


def normalize_code(value: str, *, field: str = "code", max_length: int = 64) -> str:
    """Normalize an identifier code: trimmed and uppercase, then validate it.

    Args:
        value: Code as typed.
        field: Name of the input field, reported in the error.
        max_length: Maximum number of characters.

    Returns:
        The normalized code.

    Raises:
        ValidationError: If the code is empty, too long or has invalid characters.
    """
    code = value.strip().upper()
    if not code:
        raise ValidationError(f"{field} must not be blank.", code="blank", field=field)
    if len(code) > max_length:
        raise ValidationError(
            f"{field} must have at most {max_length} characters.", code="too_long", field=field
        )
    if not CODE_PATTERN.match(code):
        raise ValidationError(
            f"{field} may only contain letters, digits, '.', '_' or '-'.",
            code="code_format",
            field=field,
        )
    return code


def required_text(value: str, *, field: str, max_length: int) -> str:
    """Trim a required text value and validate it.

    Args:
        value: Text as typed.
        field: Name of the input field, reported in the error.
        max_length: Maximum number of characters.

    Returns:
        The trimmed text.

    Raises:
        ValidationError: If the text is blank or too long.
    """
    text = value.strip()
    if not text:
        raise ValidationError(f"{field} must not be blank.", code="blank", field=field)
    if len(text) > max_length:
        raise ValidationError(
            f"{field} must have at most {max_length} characters.", code="too_long", field=field
        )
    return text


def optional_text(value: str | None, *, field: str, max_length: int) -> str | None:
    """Trim an optional text value; blank becomes ``None``.

    Args:
        value: Text as typed, or ``None``.
        field: Name of the input field, reported in the error.
        max_length: Maximum number of characters.

    Returns:
        The trimmed text, or ``None`` when blank.

    Raises:
        ValidationError: If the text is too long.
    """
    if value is None or not value.strip():
        return None
    return required_text(value, field=field, max_length=max_length)


def require_permission(role: Role, permission: Permission) -> None:
    """Stop an action that the role is not allowed to perform.

    Args:
        role: Role of the user performing the action.
        permission: Permission the action requires.

    Raises:
        PermissionDeniedError: If the role lacks the permission.
    """
    if not has_permission(role, permission):
        raise PermissionDeniedError(f"Role '{role}' lacks permission '{permission}'.")
