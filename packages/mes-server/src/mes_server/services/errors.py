"""Errors raised by the application services.

Every error carries a stable ``code`` besides its English message. The command line prints the
message; the web application looks up the code in :mod:`mes_server.web.messages` to show a
Spanish text, so wording can change without touching the services.
"""


class ServiceError(Exception):
    """Base class for errors that the caller can explain to the user.

    Attributes:
        code: Stable identifier of the error, such as ``"code_taken"``.
        field: Name of the input field the error refers to, when there is one.
    """

    code = "service_error"

    def __init__(self, message: str, *, code: str | None = None, field: str | None = None) -> None:
        """Create the error.

        Args:
            message: English description for logs and the command line.
            code: Stable identifier; defaults to the class's ``code``.
            field: Input field the error refers to.
        """
        super().__init__(message)
        if code is not None:
            self.code = code
        self.field = field


class ValidationError(ServiceError):
    """Input data breaks a business rule."""

    code = "invalid"


class AlreadyExistsError(ServiceError):
    """An object with the same unique identifier already exists."""

    code = "already_exists"


class NotFoundError(ServiceError):
    """The requested object does not exist."""

    code = "not_found"


class InUseError(ServiceError):
    """The object is referenced by production history and cannot be deleted."""

    code = "in_use"


class PermissionDeniedError(ServiceError):
    """The user's role does not allow the action."""

    code = "permission_denied"
