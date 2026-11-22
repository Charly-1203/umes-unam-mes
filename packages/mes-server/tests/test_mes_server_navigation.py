from mes_core.enums import Role
from mes_core.permissions import Permission
from mes_server.web.navigation import MODULES, ROLE_LABELS, find_module, modules_for


def test_every_role_has_a_label():
    assert set(ROLE_LABELS) == set(Role)


def test_module_paths_are_unique_and_absolute():
    paths = [module.path for module in MODULES]
    assert len(paths) == len(set(paths))
    assert all(path.startswith("/") and path != "/" for path in paths)


def test_admin_sees_every_module():
    assert modules_for(Role.ADMIN) == list(MODULES)


def test_engineer_sees_product_definition_but_not_users():
    titles = {module.title for module in modules_for(Role.PROCESS_ENGINEER)}
    assert {"Productos", "Estaciones", "Recetas"} <= titles
    assert "Usuarios" not in titles
    assert "Órdenes" not in titles


def test_supervisor_sees_orders_and_production():
    titles = {module.title for module in modules_for(Role.SUPERVISOR)}
    assert {"Órdenes", "Producción", "Downtime", "Trazabilidad"} <= titles
    assert "Recetas" not in titles


def test_operator_has_no_server_modules():
    assert modules_for(Role.OPERATOR) == []


def test_find_module():
    assert find_module("/users").permission is Permission.MANAGE_USERS
    assert find_module("/missing") is None
