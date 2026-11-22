"""Enumerations shared by every MES component.

Values are lowercase strings so they read well in JSON messages, logs and the database.
"""

from enum import StrEnum


class Role(StrEnum):
    """Permission level of a user."""

    ADMIN = "admin"
    """Manages users and system configuration."""

    PROCESS_ENGINEER = "process_engineer"
    """Defines products, stations and recipes."""

    SUPERVISOR = "supervisor"
    """Releases work orders and monitors production."""

    OPERATOR = "operator"
    """Executes work at a station."""


class RecipeStatus(StrEnum):
    """Lifecycle of a recipe version."""

    DRAFT = "draft"
    """Editable; cannot be used to produce."""

    RELEASED = "released"
    """Frozen; the version that work orders use."""

    OBSOLETE = "obsolete"
    """Replaced by a newer version; kept for traceability."""


class WorkOrderStatus(StrEnum):
    """Lifecycle of a work order."""

    CREATED = "created"
    """Received from the ERP; not yet available to the shop floor."""

    RELEASED = "released"
    """Available to the shop floor."""

    IN_PROGRESS = "in_progress"
    """At least one unit has started production."""

    PAUSED = "paused"
    """Temporarily stopped."""

    COMPLETED = "completed"
    """All planned units are finished."""

    CLOSED = "closed"
    """Reviewed and archived; no further changes."""

    CANCELLED = "cancelled"
    """Withdrawn before completion."""


class UnitStatus(StrEnum):
    """State of an individual serialized unit."""

    CREATED = "created"
    """Serial number assigned; no step executed yet."""

    IN_PROCESS = "in_process"
    """At least one step executed and the route is not finished."""

    PASSED = "passed"
    """Every step of the route finished OK."""

    FAILED = "failed"
    """A step finished NOK."""

    SCRAPPED = "scrapped"
    """Removed from production."""


class StepResult(StrEnum):
    """Outcome of executing one recipe step on one unit."""

    OK = "ok"
    NOK = "nok"
