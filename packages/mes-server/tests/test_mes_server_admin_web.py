import pytest
from nicegui.testing import user_simulation
from sqlmodel import Session, select

from mes_core.enums import Role
from mes_server.db import create_db_engine, migrate
from mes_server.db.models import Product, User
from mes_server.services import backups, users
from mes_server.web.admin_pages import describe_counts, describe_reason, format_size
from mes_server.web.app import build_root

PASSWORD = "secret123"


def add_user(engine, username, role, full_name=None):
    with Session(engine) as session:
        user = users.create_user(
            session, username=username, full_name=full_name or username.title(),
            password=PASSWORD, role=role,
        )  # fmt: skip
        session.commit()
        return user.id


async def sign_in(visitor, username):
    await visitor.open("/")
    visitor.find("Usuario").type(username)
    visitor.find("Contraseña").type(PASSWORD)
    visitor.find("Entrar").click()
    await visitor.should_see("Hola,")


async def fill_and_save(visitor, **values):
    for name, value in values.items():
        element = visitor.find(marker=f"field-{name}")
        if name == "role":
            element.elements.pop().value = value
        else:
            element.clear().type(value)
    visitor.find(marker="dialog-save").click()


# ---------------------------------------------------------------------------------------------
# Users screen (in-memory database)
# ---------------------------------------------------------------------------------------------
@pytest.fixture
async def visitor(engine):
    async with user_simulation(root=build_root(engine)) as user:
        yield user


async def test_admin_sees_users_and_marks_their_own_account(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    add_user(engine, "op1", Role.OPERATOR, "Operador Uno")
    await sign_in(visitor, "admin")
    await visitor.open("/users")
    await visitor.should_see("Operador Uno")
    await visitor.should_see("tú")
    await visitor.should_not_see(marker="delete-admin")
    await visitor.should_see(marker="delete-op1")


async def test_admin_creates_a_user(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    await sign_in(visitor, "admin")
    await visitor.open("/users")
    visitor.find(marker="user-new").click()
    await fill_and_save(
        visitor,
        username="ana.lopez",
        full_name="Ana López",
        role="supervisor",
        password="clave-segura",
        password_confirm="clave-segura",
    )
    await visitor.should_see("Usuario creado.")
    with Session(engine) as session:
        assert users.authenticate(session, "ana.lopez", "clave-segura").role == Role.SUPERVISOR


async def test_password_mismatch_is_reported(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    await sign_in(visitor, "admin")
    await visitor.open("/users")
    visitor.find(marker="user-new").click()
    await fill_and_save(
        visitor, username="ana", full_name="Ana", password="clave-uno", password_confirm="clave-dos"
    )
    error = visitor.find(marker="field-password_confirm").elements.pop().error
    assert error == "Las contraseñas no coinciden."


async def test_admin_changes_a_role(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    add_user(engine, "op1", Role.OPERATOR)
    await sign_in(visitor, "admin")
    await visitor.open("/users")
    visitor.find(marker="edit-op1").click()
    await fill_and_save(visitor, role="supervisor")
    await visitor.should_see("Cambios guardados.")
    with Session(engine) as session:
        assert users.get_user_by_username(session, "op1").role == Role.SUPERVISOR


async def test_admin_cannot_change_their_own_role(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    await sign_in(visitor, "admin")
    await visitor.open("/users")
    visitor.find(marker="edit-admin").click()
    await fill_and_save(visitor, role="operator")
    await visitor.should_see("No puedes hacer esto con tu propia cuenta.")


async def test_admin_resets_a_password(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    add_user(engine, "op1", Role.OPERATOR)
    await sign_in(visitor, "admin")
    await visitor.open("/users")
    visitor.find(marker="password-op1").click()
    await fill_and_save(visitor, password="nueva-clave", password_confirm="nueva-clave")
    await visitor.should_see("Contraseña actualizada.")
    with Session(engine) as session:
        assert users.authenticate(session, "op1", "nueva-clave") is not None


async def test_admin_deactivates_and_deletes_a_user(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    add_user(engine, "op1", Role.OPERATOR)
    await sign_in(visitor, "admin")
    await visitor.open("/users")
    visitor.find(marker="deactivate-op1").click()
    visitor.find(marker="dialog-confirm").click()
    await visitor.should_see("Usuario desactivado.")
    visitor.find(marker="show-inactive").click()
    visitor.find(marker="delete-op1").click()
    visitor.find(marker="dialog-confirm").click()
    await visitor.should_see("Usuario borrado.")
    with Session(engine) as session:
        assert users.get_user_by_username(session, "op1") is None


async def test_engineer_cannot_open_users(engine, visitor):
    add_user(engine, "eng", Role.PROCESS_ENGINEER)
    await sign_in(visitor, "eng")
    await visitor.open("/users")
    await visitor.should_see("No tienes permiso para abrir esta sección.")


async def test_admin_section_without_backups(engine, visitor):
    add_user(engine, "admin", Role.ADMIN)
    await sign_in(visitor, "admin")
    await visitor.open("/admin")
    await visitor.should_see("Los respaldos solo están disponibles")
    await visitor.should_see("No disponible: requiere respaldos.")


# ---------------------------------------------------------------------------------------------
# Administration screen (file database, real backups)
# ---------------------------------------------------------------------------------------------
@pytest.fixture
def file_db(tmp_path):
    url = f"sqlite:///{(tmp_path / 'mes.db').as_posix()}"
    migrate.upgrade(url)
    engine = create_db_engine(url)
    yield url, engine, tmp_path / "respaldos"
    engine.dispose()


@pytest.fixture
async def admin_visitor(file_db):
    url, engine, backup_dir = file_db
    async with user_simulation(
        root=build_root(engine, database_url=url, backup_dir=backup_dir)
    ) as user:
        yield user


async def test_admin_creates_a_backup(file_db, admin_visitor):
    _, engine, backup_dir = file_db
    add_user(engine, "admin", Role.ADMIN)
    await sign_in(admin_visitor, "admin")
    await admin_visitor.open("/admin")
    await admin_visitor.should_see("Aún no hay respaldos.")
    admin_visitor.find(marker="backup-create").click()
    await admin_visitor.should_see("Respaldo creado")
    await admin_visitor.should_see("Respaldo manual")
    assert len(backups.list_backups(backup_dir)) == 1


async def test_reset_button_needs_the_confirmation_word(file_db, admin_visitor):
    _, engine, _ = file_db
    add_user(engine, "admin", Role.ADMIN)
    await sign_in(admin_visitor, "admin")
    await admin_visitor.open("/admin")
    button = admin_visitor.find(marker="reset-run").elements.pop()
    assert not button.enabled
    admin_visitor.find(marker="reset-confirmation").type("REINICIAR")
    assert button.enabled


async def test_admin_resets_the_course(file_db, admin_visitor):
    _, engine, backup_dir = file_db
    add_user(engine, "admin", Role.ADMIN)
    add_user(engine, "op1", Role.OPERATOR)
    with Session(engine) as session:
        session.add(Product(code="P-1", name="Producto"))
        session.commit()
    await sign_in(admin_visitor, "admin")
    await admin_visitor.open("/admin")
    admin_visitor.find(marker="reset-level").elements.pop().value = "everything"
    await admin_visitor.should_see("1 productos")
    admin_visitor.find(marker="reset-confirmation").type("REINICIAR")
    admin_visitor.find(marker="reset-run").click()
    await admin_visitor.should_see("Curso reiniciado")
    await admin_visitor.should_see("Reinicio de curso")
    with Session(engine) as session:
        assert session.exec(select(Product)).all() == []
        assert [u.username for u in session.exec(select(User)).all()] == ["admin"]
    assert len(backups.list_backups(backup_dir)) == 1


async def test_supervisor_cannot_open_administration(file_db, admin_visitor):
    _, engine, _ = file_db
    add_user(engine, "sup", Role.SUPERVISOR)
    await sign_in(admin_visitor, "sup")
    await admin_visitor.open("/admin")
    await admin_visitor.should_see("No tienes permiso para abrir esta sección.")


# ---------------------------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("size", "text"), [(100, "1 KB"), (84_000, "82 KB"), (5 * 1024 * 1024, "5.0 MB")]
)
def test_format_size(size, text):
    assert format_size(size) == text


@pytest.mark.parametrize(
    ("reason", "text"),
    [
        ("manual", "Manual"),
        ("course-reset-production", "Antes de reiniciar (producción)"),
        ("course-reset-everything", "Antes de reiniciar (todo)"),
        ("other", "other"),
    ],
)
def test_describe_reason(reason, text):
    assert describe_reason(reason) == text


def test_describe_counts():
    assert describe_counts({"work_orders": 2, "units": 0, "products": 1}) == (
        "2 órdenes de trabajo, 1 productos"
    )
    assert describe_counts({"units": 0}) == "nada"
