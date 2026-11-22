import pytest

from mes_core.enums import Role
from mes_core.permissions import ROLE_PERMISSIONS, Permission, has_permission, permissions_for


def test_every_role_has_permissions_defined():
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_admin_has_every_permission():
    assert permissions_for(Role.ADMIN) == frozenset(Permission)


def test_only_admin_manages_users():
    holders = {role for role in Role if has_permission(role, Permission.MANAGE_USERS)}
    assert holders == {Role.ADMIN}


@pytest.mark.parametrize(
    ("role", "permission", "expected"),
    [
        (Role.PROCESS_ENGINEER, Permission.MANAGE_PRODUCT_DEFINITION, True),
        (Role.PROCESS_ENGINEER, Permission.MANAGE_WORK_ORDERS, False),
        (Role.SUPERVISOR, Permission.MANAGE_WORK_ORDERS, True),
        (Role.SUPERVISOR, Permission.MANAGE_PRODUCT_DEFINITION, False),
        (Role.SUPERVISOR, Permission.REPORT_DOWNTIME, True),
        (Role.OPERATOR, Permission.OPERATE_STATION, True),
        (Role.OPERATOR, Permission.REPORT_DOWNTIME, True),
        (Role.OPERATOR, Permission.VIEW_PRODUCTION, False),
    ],
)
def test_role_permissions(role, permission, expected):
    assert has_permission(role, permission) is expected


def test_unknown_role_has_no_permissions():
    assert permissions_for("visitor") == frozenset()
