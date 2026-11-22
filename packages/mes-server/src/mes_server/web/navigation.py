"""Modules of the web application and the permission each one requires.

The menu, the home screen and the access checks are all built from :data:`MODULES`, so adding
a screen means adding one entry here and its page builder.
"""

from dataclasses import dataclass

from mes_core.enums import Role
from mes_core.permissions import Permission, has_permission


@dataclass(frozen=True, slots=True)
class Module:
    """One section of the web application.

    Attributes:
        path: URL path of the section.
        title: Name shown in the menu.
        icon: Material icon name.
        description: One-line explanation shown on the home screen.
        permission: Permission required to open it.
        available: ``False`` while the section is still under construction.
    """

    path: str
    title: str
    icon: str
    description: str
    permission: Permission
    available: bool = False


MODULES: tuple[Module, ...] = (
    Module(
        "/products",
        "Productos",
        "inventory_2",
        "Productos y listas de materiales.",
        Permission.MANAGE_PRODUCT_DEFINITION,
        available=True,
    ),
    Module(
        "/stations",
        "Estaciones",
        "precision_manufacturing",
        "Estaciones de trabajo de la línea.",
        Permission.MANAGE_PRODUCT_DEFINITION,
        available=True,
    ),
    Module(
        "/downtime-reasons",
        "Motivos de paro",
        "report_problem",
        "Catálogo de causas de paro.",
        Permission.MANAGE_PRODUCT_DEFINITION,
        available=True,
    ),
    Module(
        "/recipes",
        "Recetas",
        "list_alt",
        "Pasos, parámetros y límites de cada producto.",
        Permission.MANAGE_PRODUCT_DEFINITION,
    ),
    Module(
        "/orders",
        "Órdenes",
        "assignment",
        "Órdenes de producción recibidas del ERP.",
        Permission.MANAGE_WORK_ORDERS,
    ),
    Module(
        "/production",
        "Producción",
        "dashboard",
        "Estado de órdenes y estaciones en tiempo real.",
        Permission.VIEW_PRODUCTION,
    ),
    Module(
        "/downtime",
        "Downtime",
        "timer_off",
        "Paros de estación y sus motivos.",
        Permission.VIEW_PRODUCTION,
    ),
    Module(
        "/traceability",
        "Trazabilidad",
        "manage_search",
        "Historial por número de serie u orden.",
        Permission.VIEW_PRODUCTION,
    ),
    Module(
        "/users",
        "Usuarios",
        "group",
        "Usuarios y roles.",
        Permission.MANAGE_USERS,
        available=True,
    ),
    Module(
        "/admin",
        "Administración",
        "admin_panel_settings",
        "Respaldos, reinicio de curso y bitácora.",
        Permission.ADMINISTER_SYSTEM,
        available=True,
    ),
)
"""Every section of the application, in menu order."""


ROLE_LABELS: dict[Role, str] = {
    Role.ADMIN: "Administrador",
    Role.PROCESS_ENGINEER: "Ingeniero de procesos",
    Role.SUPERVISOR: "Supervisor",
    Role.OPERATOR: "Operador",
}
"""Role names as shown to users."""


def modules_for(role: Role) -> list[Module]:
    """Return the sections a role may open, in menu order.

    Args:
        role: Role of the signed-in user.

    Returns:
        The permitted sections.
    """
    return [module for module in MODULES if has_permission(role, module.permission)]


def find_module(path: str) -> Module | None:
    """Find the section served at a path.

    Args:
        path: URL path.

    Returns:
        The section, or ``None`` if no section uses the path.
    """
    return next((module for module in MODULES if module.path == path), None)
