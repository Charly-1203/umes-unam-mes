import pytest
from nicegui.testing import user_simulation
from sqlmodel import Session

from mes_core.enums import Role
from mes_server.db.models import User
from mes_server.services.users import create_user
from mes_server.web.app import build_root

PASSWORD = "secret123"


def add_user(engine, username, role, full_name=None):
    with Session(engine) as session:
        create_user(
            session,
            username=username,
            full_name=full_name or username.title(),
            password=PASSWORD,
            role=role,
        )
        session.commit()


@pytest.fixture
async def visitor(engine):
    async with user_simulation(root=build_root(engine)) as user:
        yield user


async def sign_in(visitor, username, password=PASSWORD):
    await visitor.open("/")
    visitor.find("Usuario").type(username)
    visitor.find("Contraseña").type(password)
    visitor.find("Entrar").click()


async def test_visitor_sees_the_sign_in_screen(visitor):
    await visitor.open("/")
    await visitor.should_see("Entrar")
    await visitor.should_not_see("Cerrar sesión")


async def test_any_url_requires_signing_in(visitor):
    await visitor.open("/users")
    await visitor.should_see("Entrar")
    await visitor.should_not_see("Usuarios")


async def test_hint_is_shown_when_no_administrator_exists(visitor):
    await visitor.open("/")
    await visitor.should_see("Aún no hay administradores.")


async def test_hint_is_hidden_once_an_administrator_exists(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    await visitor.open("/")
    await visitor.should_not_see("Aún no hay administradores.")


async def test_successful_sign_in_shows_the_home_screen(engine, visitor):
    add_user(engine, "admin", Role.ADMIN, full_name="Ada Admin")
    await sign_in(visitor, "admin")
    await visitor.should_see("Hola, Ada Admin")
    await visitor.should_see("Estas son las secciones disponibles para tu rol.")


async def test_wrong_password_keeps_the_visitor_out(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    await sign_in(visitor, "admin", "wrong-password")
    await visitor.should_see("Usuario o contraseña incorrectos.")
    await visitor.should_not_see("Hola,")


async def test_unknown_user_keeps_the_visitor_out(visitor):
    await sign_in(visitor, "ghost")
    await visitor.should_see("Usuario o contraseña incorrectos.")


async def test_administrator_menu_includes_users(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    await sign_in(visitor, "admin")
    await visitor.should_see("Usuarios")
    await visitor.should_see("Recetas")
    await visitor.should_see("Órdenes")


async def test_engineer_menu_shows_only_permitted_modules(engine, visitor):
    add_user(engine, "eng", Role.PROCESS_ENGINEER)
    await sign_in(visitor, "eng")
    await visitor.should_see("Recetas")
    await visitor.should_not_see("Usuarios")
    await visitor.should_not_see("Órdenes")


async def test_operator_is_sent_to_the_station(engine, visitor):
    add_user(engine, "op1", Role.OPERATOR)
    await sign_in(visitor, "op1")
    await visitor.should_see("Tu trabajo se realiza en la pantalla de tu estación.")


async def test_permitted_module_opens(engine, visitor):
    add_user(engine, "eng", Role.PROCESS_ENGINEER)
    await sign_in(visitor, "eng")
    await visitor.should_see("Hola,")
    await visitor.open("/recipes")
    await visitor.should_see("Esta sección está en construcción.")


async def test_forbidden_module_shows_access_denied(engine, visitor):
    add_user(engine, "eng", Role.PROCESS_ENGINEER)
    await sign_in(visitor, "eng")
    await visitor.should_see("Hola,")
    await visitor.open("/users")
    await visitor.should_see("No tienes permiso para abrir esta sección.")


async def test_sign_out_returns_to_the_sign_in_screen(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    await sign_in(visitor, "admin")
    await visitor.should_see("Hola,")
    visitor.find(marker="sign-out").click()
    await visitor.should_see("Entrar")


async def test_deactivated_user_is_signed_out_on_next_page(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    await sign_in(visitor, "admin")
    await visitor.should_see("Hola,")
    with Session(engine) as session:
        user = session.get(User, 1)
        user.is_active = False
        session.commit()
    await visitor.open("/")
    await visitor.should_see("Entrar")


async def test_active_section_is_highlighted_in_the_menu(engine, visitor):
    add_user(engine, "eng", Role.PROCESS_ENGINEER)
    await sign_in(visitor, "eng")
    await visitor.should_see("Hola,")
    await visitor.open("/recipes")
    await visitor.should_see("Esta sección está en construcción.")
    active = [
        element
        for element in visitor.find("Recetas").elements
        if "mes-nav-item--active" in (element.parent_slot.parent.classes or [])
    ]
    assert active, "the Recetas menu item should be marked as active"


async def test_top_bar_shows_the_current_section(engine, visitor):
    add_user(engine, "eng", Role.PROCESS_ENGINEER)
    await sign_in(visitor, "eng")
    await visitor.should_see("Hola,")
    await visitor.open("/stations")
    await visitor.should_see("Estaciones de trabajo de la línea.")
    await visitor.should_see("UNAM-MES")


async def test_sign_in_screen_explains_the_isa95_levels(visitor):
    await visitor.open("/")
    for level in ("ERP", "MES", "Estación de trabajo", "PLC"):
        await visitor.should_see(level)
