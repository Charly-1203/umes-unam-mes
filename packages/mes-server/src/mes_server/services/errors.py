"""Errors raised by the application services."""


class ServiceError(Exception):
    """Base class for errors that the caller can explain to the user."""


class ValidationError(ServiceError):
    """Input data breaks a business rule."""


class AlreadyExistsError(ServiceError):
    """An object with the same unique identifier already exists."""
