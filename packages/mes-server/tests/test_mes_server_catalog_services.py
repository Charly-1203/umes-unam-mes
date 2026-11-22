from datetime import UTC, datetime

import pytest

from mes_core.enums import Role
from mes_server.db.models import DowntimeEvent, Recipe, RecipeStep, WorkOrder
from mes_server.services import downtime_reasons, products, stations
from mes_server.services.errors import (
    AlreadyExistsError,
    InUseError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from mes_server.services.validation import normalize_code, optional_text, required_text


# ---------------------------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(("raw", "expected"), [(" p-100 ", "P-100"), ("st_10.a", "ST_10.A")])
def test_codes_are_trimmed_and_uppercased(raw, expected):
    assert normalize_code(raw) == expected


@pytest.mark.parametrize(
    ("raw", "error_code"),
    [("", "blank"), ("   ", "blank"), ("with space", "code_format"), ("-X", "code_format"),
     ("ÑANDÚ", "code_format"), ("X" * 65, "too_long")],
)  # fmt: skip
def test_invalid_codes_are_rejected_with_a_code(raw, error_code):
    with pytest.raises(ValidationError) as exc:
        normalize_code(raw, field="code")
    assert exc.value.code == error_code
    assert exc.value.field == "code"


def test_required_text_is_trimmed():
    assert required_text("  Hola ", field="name", max_length=10) == "Hola"


def test_optional_text_blank_becomes_none():
    assert optional_text("   ", field="description", max_length=10) is None
    assert optional_text(None, field="description", max_length=10) is None


def test_optional_text_too_long_is_rejected():
    with pytest.raises(ValidationError) as exc:
        optional_text("x" * 11, field="description", max_length=10)
    assert exc.value.code == "too_long"


# ---------------------------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------------------------
def new_product(session, code="P-100", name="Producto demo"):
    product = products.create_product(session, code=code, name=name)
    session.commit()
    return product


def test_create_product(session):
    product = products.create_product(session, code=" p-100 ", name=" Producto ", description="  ")
    session.commit()
    assert (product.code, product.name, product.description) == ("P-100", "Producto", None)
    assert product.is_active


def test_product_code_must_be_unique(session):
    new_product(session, "P-100")
    with pytest.raises(AlreadyExistsError) as exc:
        products.create_product(session, code="p-100", name="Otro")
    assert exc.value.field == "code"


def test_product_name_is_required(session):
    with pytest.raises(ValidationError) as exc:
        products.create_product(session, code="P-1", name="  ")
    assert exc.value.field == "name"


def test_update_product_keeps_the_code(session):
    product = new_product(session)
    products.update_product(session, product.id, name="Nuevo nombre", description="Detalle")
    session.commit()
    stored = products.get_product(session, product.id)
    assert (stored.code, stored.name, stored.description) == ("P-100", "Nuevo nombre", "Detalle")


def test_missing_product_raises_not_found(session):
    with pytest.raises(NotFoundError):
        products.get_product(session, 999)


def test_inactive_products_are_hidden_unless_requested(session):
    active = new_product(session, "A-1")
    inactive = new_product(session, "B-1")
    products.set_product_active(session, inactive.id, False)
    session.commit()
    assert [p.code for p in products.list_products(session)] == [active.code]
    assert [p.code for p in products.list_products(session, include_inactive=True)] == [
        "A-1",
        "B-1",
    ]


def test_reactivating_a_product(session):
    product = new_product(session)
    products.set_product_active(session, product.id, False)
    products.set_product_active(session, product.id, True)
    session.commit()
    assert products.get_product(session, product.id).is_active


def test_admin_can_delete_an_unused_product_with_its_bom(session):
    product = new_product(session)
    products.add_bom_item(session, product.id, component_code="X", quantity=1)
    session.commit()
    products.delete_product(session, product.id, actor_role=Role.ADMIN)
    session.commit()
    assert products.list_products(session, include_inactive=True) == []


@pytest.mark.parametrize("role", [Role.PROCESS_ENGINEER, Role.SUPERVISOR, Role.OPERATOR])
def test_only_admin_can_delete_a_product(session, role):
    product = new_product(session)
    with pytest.raises(PermissionDeniedError):
        products.delete_product(session, product.id, actor_role=role)


def test_product_with_history_cannot_be_deleted(session):
    product = new_product(session)
    session.add(WorkOrder(order_number="WO-1", product_id=product.id, quantity=1))
    session.add(Recipe(product_id=product.id, name="Receta"))
    session.commit()
    assert products.product_usage(session, product.id) == {"recipes": 1, "work orders": 1}
    with pytest.raises(InUseError) as exc:
        products.delete_product(session, product.id, actor_role=Role.ADMIN)
    assert "1 recipes" in str(exc.value)
    assert products.get_product(session, product.id) is not None


def test_unused_product_has_no_usage(session):
    assert products.product_usage(session, new_product(session).id) == {}


# ---------------------------------------------------------------------------------------------
# Bill of materials
# ---------------------------------------------------------------------------------------------
def test_add_and_list_bom_items(session):
    product = new_product(session)
    products.add_bom_item(session, product.id, component_code="screw-m4", quantity="4")
    products.add_bom_item(
        session, product.id, component_code="housing", quantity=1, description="Carcasa"
    )
    session.commit()
    items = products.list_bom_items(session, product.id)
    assert [(i.component_code, i.quantity, i.unit_of_measure) for i in items] == [
        ("HOUSING", 1.0, "pcs"),
        ("SCREW-M4", 4.0, "pcs"),
    ]


@pytest.mark.parametrize(
    ("quantity", "code"),
    [(0, "not_positive"), (-1, "not_positive"), ("abc", "not_a_number"), (None, "not_a_number")],
)
def test_invalid_quantities_are_rejected(session, quantity, code):
    product = new_product(session)
    with pytest.raises(ValidationError) as exc:
        products.add_bom_item(session, product.id, component_code="X", quantity=quantity)
    assert exc.value.code == code
    assert exc.value.field == "quantity"


def test_component_is_unique_per_product(session):
    product = new_product(session)
    products.add_bom_item(session, product.id, component_code="X", quantity=1)
    with pytest.raises(AlreadyExistsError) as exc:
        products.add_bom_item(session, product.id, component_code="x", quantity=2)
    assert exc.value.field == "component_code"


def test_bom_item_for_missing_product_is_rejected(session):
    with pytest.raises(NotFoundError):
        products.add_bom_item(session, 999, component_code="X", quantity=1)


def test_update_bom_item(session):
    product = new_product(session)
    item = products.add_bom_item(session, product.id, component_code="X", quantity=1)
    session.commit()
    products.update_bom_item(
        session, item.id, component_code="Y", quantity=2.5, unit_of_measure="kg", description="d"
    )
    session.commit()
    stored = products.list_bom_items(session, product.id)[0]
    assert (stored.component_code, stored.quantity, stored.unit_of_measure) == ("Y", 2.5, "kg")


def test_update_bom_item_keeps_its_own_code(session):
    product = new_product(session)
    item = products.add_bom_item(session, product.id, component_code="X", quantity=1)
    products.update_bom_item(
        session, item.id, component_code="X", quantity=3, unit_of_measure="pcs"
    )
    assert item.quantity == 3


def test_update_bom_item_cannot_duplicate_another_line(session):
    product = new_product(session)
    products.add_bom_item(session, product.id, component_code="X", quantity=1)
    second = products.add_bom_item(session, product.id, component_code="Y", quantity=1)
    with pytest.raises(AlreadyExistsError):
        products.update_bom_item(
            session, second.id, component_code="X", quantity=1, unit_of_measure="pcs"
        )


def test_delete_bom_item(session):
    product = new_product(session)
    item = products.add_bom_item(session, product.id, component_code="X", quantity=1)
    session.commit()
    products.delete_bom_item(session, item.id)
    session.commit()
    assert products.list_bom_items(session, product.id) == []


@pytest.mark.parametrize("action", ["update", "delete"])
def test_missing_bom_item_raises_not_found(session, action):
    with pytest.raises(NotFoundError):
        if action == "delete":
            products.delete_bom_item(session, 999)
        else:
            products.update_bom_item(
                session, 999, component_code="X", quantity=1, unit_of_measure="pcs"
            )


# ---------------------------------------------------------------------------------------------
# Stations
# ---------------------------------------------------------------------------------------------
def new_station(session, code="ST-10"):
    station = stations.create_station(session, code=code, name=f"Estación {code}")
    session.commit()
    return station


def test_create_and_update_station(session):
    station = new_station(session, "st-10")
    assert station.code == "ST-10"
    stations.update_station(session, station.id, name="Atornillado", description="Celda 1")
    session.commit()
    assert stations.get_station(session, station.id).name == "Atornillado"


def test_station_code_is_limited_to_32_characters(session):
    with pytest.raises(ValidationError) as exc:
        stations.create_station(session, code="X" * 33, name="Larga")
    assert exc.value.code == "too_long"


def test_station_code_must_be_unique(session):
    new_station(session)
    with pytest.raises(AlreadyExistsError):
        stations.create_station(session, code="ST-10", name="Duplicada")


def test_deactivated_station_is_hidden(session):
    station = new_station(session)
    stations.set_station_active(session, station.id, False)
    session.commit()
    assert stations.list_stations(session) == []
    assert len(stations.list_stations(session, include_inactive=True)) == 1


def test_station_used_by_a_recipe_cannot_be_deleted(session):
    station = new_station(session)
    product = new_product(session)
    recipe = Recipe(product_id=product.id, name="Receta")
    recipe.steps.append(RecipeStep(sequence=1, station_id=station.id, operation="OP", name="Paso"))
    session.add(recipe)
    session.commit()
    assert stations.station_usage(session, station.id) == {"recipe steps": 1}
    with pytest.raises(InUseError):
        stations.delete_station(session, station.id, actor_role=Role.ADMIN)


def test_admin_can_delete_an_unused_station(session):
    station = new_station(session)
    stations.delete_station(session, station.id, actor_role=Role.ADMIN)
    session.commit()
    with pytest.raises(NotFoundError):
        stations.get_station(session, station.id)


def test_engineer_cannot_delete_a_station(session):
    station = new_station(session)
    with pytest.raises(PermissionDeniedError):
        stations.delete_station(session, station.id, actor_role=Role.PROCESS_ENGINEER)


# ---------------------------------------------------------------------------------------------
# Downtime reasons
# ---------------------------------------------------------------------------------------------
def new_reason(session, code="NO_MATERIAL"):
    reason = downtime_reasons.create_reason(session, code=code, description="Sin material")
    session.commit()
    return reason


def test_create_and_update_reason(session):
    reason = new_reason(session, "no_material")
    assert reason.code == "NO_MATERIAL"
    downtime_reasons.update_reason(session, reason.id, description="Falta de material")
    session.commit()
    assert downtime_reasons.get_reason(session, reason.id).description == "Falta de material"


def test_reason_description_is_required(session):
    with pytest.raises(ValidationError):
        downtime_reasons.create_reason(session, code="X", description=" ")


def test_reason_code_must_be_unique(session):
    new_reason(session)
    with pytest.raises(AlreadyExistsError):
        downtime_reasons.create_reason(session, code="NO_MATERIAL", description="Otra")


def test_deactivated_reason_is_hidden(session):
    reason = new_reason(session)
    downtime_reasons.set_reason_active(session, reason.id, False)
    session.commit()
    assert downtime_reasons.list_reasons(session) == []
    assert len(downtime_reasons.list_reasons(session, include_inactive=True)) == 1


def test_reason_used_by_downtime_cannot_be_deleted(session):
    reason = new_reason(session)
    station = new_station(session)
    session.add(
        DowntimeEvent(
            station_id=station.id, reason_id=reason.id, started_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
    )
    session.commit()
    assert downtime_reasons.reason_usage(session, reason.id) == {"downtime events": 1}
    with pytest.raises(InUseError):
        downtime_reasons.delete_reason(session, reason.id, actor_role=Role.ADMIN)


def test_admin_can_delete_an_unused_reason(session):
    reason = new_reason(session)
    downtime_reasons.delete_reason(session, reason.id, actor_role=Role.ADMIN)
    session.commit()
    assert downtime_reasons.list_reasons(session, include_inactive=True) == []


def test_supervisor_cannot_delete_a_reason(session):
    reason = new_reason(session)
    with pytest.raises(PermissionDeniedError):
        downtime_reasons.delete_reason(session, reason.id, actor_role=Role.SUPERVISOR)
