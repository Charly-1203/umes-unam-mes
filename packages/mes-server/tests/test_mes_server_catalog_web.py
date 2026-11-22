import pytest
from nicegui.testing import user_simulation
from sqlmodel import Session

from mes_core.enums import Role
from mes_server.db.models import Recipe, WorkOrder
from mes_server.services import downtime_reasons, products, stations
from mes_server.services.users import create_user
from mes_server.web.app import build_root

PASSWORD = "secret123"


@pytest.fixture
async def visitor(engine):
    async with user_simulation(root=build_root(engine)) as user:
        yield user


def add_user(engine, username, role):
    with Session(engine) as session:
        create_user(
            session, username=username, full_name=username.title(), password=PASSWORD, role=role
        )
        session.commit()


async def sign_in_as(engine, visitor, role, username="tester"):
    add_user(engine, username, role)
    await visitor.open("/")
    visitor.find("Usuario").type(username)
    visitor.find("Contraseña").type(PASSWORD)
    visitor.find("Entrar").click()
    await visitor.should_see("Hola,")


def seed_product(engine, code="P-100", name="Producto demo"):
    with Session(engine) as session:
        product = products.create_product(session, code=code, name=name)
        session.commit()
        return product.id


async def fill_and_save(visitor, **values):
    for name, value in values.items():
        visitor.find(marker=f"field-{name}").clear().type(value)
    visitor.find(marker="dialog-save").click()


# ---------------------------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------------------------
async def test_products_screen_shows_an_empty_state(engine, visitor):
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/products")
    await visitor.should_see("Aún no hay productos.")


async def test_engineer_creates_a_product(engine, visitor):
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/products")
    visitor.find(marker="catalog-new").click()
    await fill_and_save(visitor, code="p-100", name="Ensamble demo")
    await visitor.should_see("P-100")
    await visitor.should_see("Ensamble demo")
    await visitor.should_see("Registro creado.")


async def test_blank_name_is_reported_under_the_field(engine, visitor):
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/products")
    visitor.find(marker="catalog-new").click()
    await fill_and_save(visitor, code="P-1")
    assert visitor.find(marker="field-name").elements.pop().error == "El nombre es obligatorio."


async def test_duplicate_code_is_reported(engine, visitor):
    seed_product(engine, "P-100")
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/products")
    visitor.find(marker="catalog-new").click()
    await fill_and_save(visitor, code="P-100", name="Otro")
    error = visitor.find(marker="field-code").elements.pop().error
    assert error == "Ya existe un registro con ese código."


async def test_engineer_edits_a_product_name(engine, visitor):
    seed_product(engine, "P-100", "Nombre viejo")
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/products")
    visitor.find(marker="edit-P-100").click()
    await fill_and_save(visitor, name="Nombre nuevo")
    await visitor.should_see("Nombre nuevo")
    with Session(engine) as session:
        assert products.list_products(session)[0].name == "Nombre nuevo"


async def test_deactivated_product_disappears_until_inactive_are_shown(engine, visitor):
    seed_product(engine, "P-100")
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/products")
    visitor.find(marker="deactivate-P-100").click()
    visitor.find(marker="dialog-confirm").click()
    await visitor.should_see("Desactivado.")
    await visitor.should_not_see(marker="edit-P-100")
    visitor.find(marker="show-inactive").click()
    await visitor.should_see("Inactivo")
    visitor.find(marker="activate-P-100").click()
    await visitor.should_see("Activado.")


async def test_engineer_has_no_delete_button(engine, visitor):
    seed_product(engine, "P-100")
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/products")
    await visitor.should_see(marker="edit-P-100")
    await visitor.should_not_see(marker="delete-P-100")


async def test_admin_deletes_an_unused_product(engine, visitor):
    seed_product(engine, "P-100")
    await sign_in_as(engine, visitor, Role.ADMIN)
    await visitor.open("/products")
    visitor.find(marker="delete-P-100").click()
    visitor.find(marker="dialog-confirm").click()
    await visitor.should_see("Registro borrado.")
    await visitor.should_see("Aún no hay productos.")


async def test_admin_cannot_delete_a_product_with_history(engine, visitor):
    product_id = seed_product(engine, "P-100")
    with Session(engine) as session:
        session.add(WorkOrder(order_number="WO-1", product_id=product_id, quantity=1))
        session.add(Recipe(product_id=product_id, name="Receta"))
        session.commit()
    await sign_in_as(engine, visitor, Role.ADMIN)
    await visitor.open("/products")
    visitor.find(marker="delete-P-100").click()
    await visitor.should_see("No se puede borrar P-100")
    await visitor.should_see("1 receta y 1 orden de trabajo", retries=3)


async def test_operator_cannot_open_products(engine, visitor):
    await sign_in_as(engine, visitor, Role.OPERATOR)
    await visitor.open("/products")
    await visitor.should_see("No tienes permiso para abrir esta sección.")


# ---------------------------------------------------------------------------------------------
# Bill of materials
# ---------------------------------------------------------------------------------------------
async def test_product_detail_manages_the_bill_of_materials(engine, visitor):
    product_id = seed_product(engine, "P-100", "Ensamble")
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open(f"/products/{product_id}")
    await visitor.should_see("P-100 · Ensamble")
    await visitor.should_see("Este producto aún no tiene componentes.")

    visitor.find(marker="bom-add").click()
    await fill_and_save(visitor, component_code="screw-m4", description="Tornillo")
    await visitor.should_see("SCREW-M4")
    with Session(engine) as session:
        assert products.list_bom_items(session, product_id)[0].quantity == 1

    visitor.find(marker="bom-delete-SCREW-M4").click()
    visitor.find(marker="dialog-confirm").click()
    await visitor.should_see("Componente quitado.")
    await visitor.should_see("Este producto aún no tiene componentes.")


async def test_detail_button_opens_the_bill_of_materials(engine, visitor):
    seed_product(engine, "P-100", "Ensamble")
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/products")
    visitor.find(marker="detail-P-100").click()
    await visitor.should_see("Lista de materiales")


async def test_unknown_product_shows_a_message(engine, visitor):
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/products/999")
    await visitor.should_see("El producto no existe.")


async def test_operator_cannot_open_a_product_detail(engine, visitor):
    product_id = seed_product(engine)
    await sign_in_as(engine, visitor, Role.OPERATOR)
    await visitor.open(f"/products/{product_id}")
    await visitor.should_see("No tienes permiso para abrir esta sección.")


# ---------------------------------------------------------------------------------------------
# Stations and downtime reasons
# ---------------------------------------------------------------------------------------------
async def test_engineer_creates_a_station(engine, visitor):
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/stations")
    visitor.find(marker="catalog-new").click()
    await fill_and_save(visitor, code="st-10", name="Atornillado")
    await visitor.should_see("ST-10")
    with Session(engine) as session:
        assert stations.list_stations(session)[0].name == "Atornillado"


async def test_engineer_creates_a_downtime_reason(engine, visitor):
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/downtime-reasons")
    visitor.find(marker="catalog-new").click()
    await fill_and_save(visitor, code="no_material", description="Sin material")
    await visitor.should_see("NO_MATERIAL")
    with Session(engine) as session:
        assert downtime_reasons.list_reasons(session)[0].description == "Sin material"


async def test_invalid_code_format_is_explained(engine, visitor):
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/stations")
    visitor.find(marker="catalog-new").click()
    await fill_and_save(visitor, code="con espacio", name="X")
    error = visitor.find(marker="field-code").elements.pop().error
    assert "sin espacios" in error


async def test_products_list_shows_the_number_of_components(engine, visitor):
    product_id = seed_product(engine, "P-100")
    seed_product(engine, "P-200")
    with Session(engine) as session:
        products.add_bom_item(session, product_id, component_code="A", quantity=1)
        products.add_bom_item(session, product_id, component_code="B", quantity=2)
        session.commit()
    await sign_in_as(engine, visitor, Role.PROCESS_ENGINEER)
    await visitor.open("/products")
    await visitor.should_see("2")
    await visitor.should_see("0")
