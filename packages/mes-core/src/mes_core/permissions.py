"""What each role is allowed to do.

Screens and services ask for a :class:`Permission`, never for a role. Changing what a role may
do therefore only requires editing :data:`ROLE_PERMISSIONS`.
"""

from collections.abc import Mapping
from enum import StrEnum

from mes_core.enums import Role


class Permission(StrEnum):
    """Capability that a screen or an action requires."""

    MANAGE_USERS = "manage_users"
    """Create users and change their role or status."""

    MANAGE_PRODUCT_DEFINITION = "manage_product_definition"
    """Maintain products, bills of materials, stations and recipes."""

    MANAGE_WORK_ORDERS = "manage_work_orders"
    """Release, pause, cancel and close work orders."""

    VIEW_PRODUCTION = "view_production"
    """See production status, downtime and traceability."""

    REPORT_DOWNTIME = "report_downtime"
    """Record downtime events and assign their reasons."""

    OPERATE_STATION = "operate_station"
    """Execute work at a station."""


ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.PROCESS_ENGINEER: frozenset(
        {Permission.MANAGE_PRODUCT_DEFINITION, Permission.VIEW_PRODUCTION}
    ),
    Role.SUPERVISOR: frozenset(
        {Permission.MANAGE_WORK_ORDERS, Permission.VIEW_PRODUCTION, Permission.REPORT_DOWNTIME}
    ),
    Role.OPERATOR: frozenset({Permission.OPERATE_STATION, Permission.REPORT_DOWNTIME}),
}
"""Permissions granted to each role."""


def permissions_for(role: Role) -> frozenset[Permission]:
    """Return every permission granted to a role.

    Args:
        role: Role to look up.

    Returns:
        The role's permissions; empty for an unknown role.
    """
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: Role, permission: Permission) -> bool:
    """Tell whether a role grants a permission.

    Args:
        role: Role of the user.
        permission: Required permission.

    Returns:
        ``True`` when the role grants the permission.
    """
    return permission in permissions_for(role)
