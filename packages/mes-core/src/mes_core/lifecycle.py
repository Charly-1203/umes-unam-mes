"""Allowed status transitions.

Keeping the rules here, instead of inside the server, lets every component validate a status
change the same way and makes the lifecycle easy to read and to teach.
"""

from collections.abc import Mapping

from mes_core.enums import RecipeStatus, UnitStatus, WorkOrderStatus

WORK_ORDER_TRANSITIONS: Mapping[WorkOrderStatus, frozenset[WorkOrderStatus]] = {
    WorkOrderStatus.CREATED: frozenset({WorkOrderStatus.RELEASED, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.RELEASED: frozenset({WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.IN_PROGRESS: frozenset({WorkOrderStatus.PAUSED, WorkOrderStatus.COMPLETED}),
    WorkOrderStatus.PAUSED: frozenset({WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.COMPLETED: frozenset({WorkOrderStatus.CLOSED}),
    WorkOrderStatus.CLOSED: frozenset(),
    WorkOrderStatus.CANCELLED: frozenset(),
}
"""For each work order status, the statuses it may move to."""

RECIPE_TRANSITIONS: Mapping[RecipeStatus, frozenset[RecipeStatus]] = {
    RecipeStatus.DRAFT: frozenset({RecipeStatus.RELEASED}),
    RecipeStatus.RELEASED: frozenset({RecipeStatus.OBSOLETE}),
    RecipeStatus.OBSOLETE: frozenset(),
}
"""For each recipe status, the statuses it may move to."""

UNIT_TRANSITIONS: Mapping[UnitStatus, frozenset[UnitStatus]] = {
    UnitStatus.CREATED: frozenset({UnitStatus.IN_PROCESS, UnitStatus.SCRAPPED}),
    UnitStatus.IN_PROCESS: frozenset({UnitStatus.PASSED, UnitStatus.FAILED, UnitStatus.SCRAPPED}),
    UnitStatus.FAILED: frozenset({UnitStatus.IN_PROCESS, UnitStatus.SCRAPPED}),
    UnitStatus.PASSED: frozenset(),
    UnitStatus.SCRAPPED: frozenset(),
}
"""For each unit status, the statuses it may move to. A failed unit may be reworked."""


class InvalidTransitionError(ValueError):
    """Raised when a status change is not allowed by its lifecycle."""

    def __init__(self, current: str, target: str) -> None:
        """Build the error message.

        Args:
            current: Status the object is in.
            target: Status that was requested.
        """
        super().__init__(f"Transition from '{current}' to '{target}' is not allowed.")
        self.current = current
        self.target = target


def can_transition[S](transitions: Mapping[S, frozenset[S]], current: S, target: S) -> bool:
    """Tell whether ``current`` may move to ``target``.

    Args:
        transitions: Lifecycle table, such as :data:`WORK_ORDER_TRANSITIONS`.
        current: Status the object is in.
        target: Status that is requested.

    Returns:
        ``True`` when the transition is allowed.
    """
    return target in transitions.get(current, frozenset())


def ensure_transition[S](transitions: Mapping[S, frozenset[S]], current: S, target: S) -> S:
    """Validate a status change and return the new status.

    Args:
        transitions: Lifecycle table, such as :data:`WORK_ORDER_TRANSITIONS`.
        current: Status the object is in.
        target: Status that is requested.

    Returns:
        ``target``, so the call can be used in an assignment.

    Raises:
        InvalidTransitionError: If the lifecycle does not allow the change.
    """
    if not can_transition(transitions, current, target):
        raise InvalidTransitionError(str(current), str(target))
    return target


def is_terminal[S](transitions: Mapping[S, frozenset[S]], status: S) -> bool:
    """Tell whether ``status`` has no further transitions.

    Args:
        transitions: Lifecycle table.
        status: Status to check.

    Returns:
        ``True`` when the status is final.
    """
    return not transitions.get(status)
