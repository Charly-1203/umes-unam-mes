from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlmodel import select

from mes_core.enums import RecipeStatus, Role, StepResult, UnitStatus, WorkOrderStatus
from mes_core.lifecycle import InvalidTransitionError
from mes_core.limits import ParameterLimit
from mes_server.db.models import (
    BomItem,
    DowntimeEvent,
    DowntimeReason,
    ExecutionRecord,
    Product,
    Recipe,
    RecipeStep,
    Station,
    Unit,
    User,
    WorkOrder,
)


# ---------------------------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------------------------
def add_product(session, code="P-100"):
    product = Product(code=code, name="Demo product")
    session.add(product)
    session.commit()
    return product


def add_station(session, code="ST-10"):
    station = Station(code=code, name=f"Station {code}")
    session.add(station)
    session.commit()
    return station


def add_recipe_with_steps(session, product, station, steps=2):
    recipe = Recipe(product_id=product.id, name="Demo recipe")
    for sequence in range(steps, 0, -1):  # inserted out of order on purpose
        recipe.steps.append(
            RecipeStep(
                sequence=sequence,
                station_id=station.id,
                operation="SCREW",
                name=f"Step {sequence}",
                parameters=[{"name": "torque", "minimum": 5.0, "maximum": 7.0, "unit": "N·m"}],
            )
        )
    session.add(recipe)
    session.commit()
    return recipe


def add_work_order(session, product, number="WO-1", quantity=10):
    order = WorkOrder(order_number=number, product_id=product.id, quantity=quantity)
    session.add(order)
    session.commit()
    return order


# ---------------------------------------------------------------------------------------------
# Product and bill of materials
# ---------------------------------------------------------------------------------------------
def test_product_with_bill_of_materials_round_trip(session):
    product = Product(code="P-100", name="Demo product")
    product.bom_items = [
        BomItem(component_code="SCREW-M4", quantity=4),
        BomItem(component_code="HOUSING", quantity=1, description="Plastic housing"),
    ]
    session.add(product)
    session.commit()
    session.expire_all()

    stored = session.exec(select(Product).where(Product.code == "P-100")).one()
    assert {item.component_code for item in stored.bom_items} == {"SCREW-M4", "HOUSING"}
    assert all(item.unit_of_measure == "pcs" for item in stored.bom_items)


def test_product_code_is_unique(session):
    add_product(session, "P-100")
    session.add(Product(code="P-100", name="Duplicate"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_bom_quantity_must_be_positive(session):
    product = add_product(session)
    session.add(BomItem(product_id=product.id, component_code="X", quantity=0))
    with pytest.raises(IntegrityError):
        session.commit()


def test_bom_component_is_unique_per_product(session):
    product = add_product(session)
    session.add_all(
        [
            BomItem(product_id=product.id, component_code="X", quantity=1),
            BomItem(product_id=product.id, component_code="X", quantity=2),
        ]
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_foreign_keys_are_enforced(session):
    session.add(BomItem(product_id=999, component_code="X", quantity=1))
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_a_product_deletes_its_bill_of_materials(session):
    product = add_product(session)
    product.bom_items.append(BomItem(component_code="X", quantity=1))
    session.commit()

    session.delete(product)
    session.commit()
    assert session.exec(select(BomItem)).all() == []


# ---------------------------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------------------------
def test_recipe_steps_are_ordered_by_sequence(session):
    recipe = add_recipe_with_steps(session, add_product(session), add_station(session), steps=3)
    session.expire_all()
    assert [step.sequence for step in session.get(Recipe, recipe.id).steps] == [1, 2, 3]


def test_new_recipe_is_draft_version_one(session):
    recipe = add_recipe_with_steps(session, add_product(session), add_station(session))
    assert recipe.status is RecipeStatus.DRAFT
    assert recipe.version == 1
    assert recipe.released_at is None


def test_step_sequence_is_unique_within_a_recipe(session):
    recipe = add_recipe_with_steps(session, add_product(session), add_station(session), steps=1)
    session.add(
        RecipeStep(
            recipe_id=recipe.id,
            sequence=1,
            station_id=recipe.steps[0].station_id,
            operation="TEST",
            name="Duplicate",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_recipe_version_is_unique_per_product(session):
    product = add_product(session)
    session.add_all(
        [
            Recipe(product_id=product.id, version=1, name="A"),
            Recipe(product_id=product.id, version=1, name="B"),
        ]
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_two_products_can_share_a_version_number(session):
    first, second = add_product(session, "P-1"), add_product(session, "P-2")
    session.add_all(
        [
            Recipe(product_id=first.id, version=1, name="A"),
            Recipe(product_id=second.id, version=1, name="B"),
        ]
    )
    session.commit()


def test_releasing_a_recipe_records_the_time(session):
    recipe = add_recipe_with_steps(session, add_product(session), add_station(session))
    recipe.change_status(RecipeStatus.RELEASED)
    session.commit()
    assert recipe.status is RecipeStatus.RELEASED
    assert recipe.released_at is not None


def test_recipe_without_steps_cannot_be_released(session):
    recipe = Recipe(product_id=add_product(session).id, name="Empty")
    session.add(recipe)
    session.commit()
    with pytest.raises(ValueError, match="at least one step"):
        recipe.change_status(RecipeStatus.RELEASED)
    assert recipe.status is RecipeStatus.DRAFT


def test_obsolete_recipe_cannot_return_to_draft(session):
    recipe = add_recipe_with_steps(session, add_product(session), add_station(session))
    recipe.change_status(RecipeStatus.RELEASED)
    recipe.change_status(RecipeStatus.OBSOLETE)
    with pytest.raises(InvalidTransitionError):
        recipe.change_status(RecipeStatus.DRAFT)


def test_deleting_a_recipe_deletes_its_steps(session):
    recipe = add_recipe_with_steps(session, add_product(session), add_station(session))
    session.delete(recipe)
    session.commit()
    assert session.exec(select(RecipeStep)).all() == []


def test_step_parameters_become_limits(session):
    recipe = add_recipe_with_steps(session, add_product(session), add_station(session), steps=1)
    session.expire_all()
    step = session.get(Recipe, recipe.id).steps[0]
    assert step.limits() == [ParameterLimit("torque", minimum=5.0, maximum=7.0, unit="N·m")]
    assert step.limits()[0].evaluate(6.0) is StepResult.OK


def test_step_without_parameters_has_no_limits():
    assert RecipeStep(sequence=1, station_id=1, operation="SCAN", name="Scan").limits() == []


def test_invalid_stored_parameters_are_reported():
    step = RecipeStep(
        sequence=1,
        station_id=1,
        operation="SCREW",
        name="Bad",
        parameters=[{"name": "torque", "minimum": 9, "maximum": 1}],
    )
    with pytest.raises(ValueError):
        step.limits()


def test_interlock_flag_defaults_to_off(session):
    recipe = add_recipe_with_steps(session, add_product(session), add_station(session), steps=1)
    assert recipe.steps[0].requires_previous_ok is False


# ---------------------------------------------------------------------------------------------
# Work orders and units
# ---------------------------------------------------------------------------------------------
def test_new_work_order_is_created(session):
    order = add_work_order(session, add_product(session))
    assert order.status is WorkOrderStatus.CREATED
    assert order.recipe_id is None


def test_work_order_quantity_must_be_positive(session):
    session.add(WorkOrder(order_number="WO-0", product_id=add_product(session).id, quantity=0))
    with pytest.raises(IntegrityError):
        session.commit()


def test_work_order_number_is_unique(session):
    product = add_product(session)
    add_work_order(session, product, "WO-1")
    session.add(WorkOrder(order_number="WO-1", product_id=product.id, quantity=1))
    with pytest.raises(IntegrityError):
        session.commit()


def test_work_order_lifecycle_records_timestamps(session):
    order = add_work_order(session, add_product(session))

    order.change_status(WorkOrderStatus.RELEASED)
    assert order.released_at is not None

    order.change_status(WorkOrderStatus.IN_PROGRESS)
    first_start = order.started_at
    assert first_start is not None

    order.change_status(WorkOrderStatus.PAUSED)
    order.change_status(WorkOrderStatus.IN_PROGRESS)
    assert order.started_at == first_start, "resuming must not reset the start time"

    order.change_status(WorkOrderStatus.COMPLETED)
    assert order.completed_at is not None
    session.commit()


def test_work_order_cannot_skip_release(session):
    order = add_work_order(session, add_product(session))
    with pytest.raises(InvalidTransitionError):
        order.change_status(WorkOrderStatus.IN_PROGRESS)
    assert order.status is WorkOrderStatus.CREATED


def test_units_belong_to_their_work_order(session):
    order = add_work_order(session, add_product(session))
    order.units = [Unit(serial_number="SN-0001"), Unit(serial_number="SN-0002")]
    session.commit()
    session.expire_all()
    assert len(session.get(WorkOrder, order.id).units) == 2


def test_serial_number_is_unique(session):
    order = add_work_order(session, add_product(session))
    session.add_all(
        [
            Unit(serial_number="SN-1", work_order_id=order.id),
            Unit(serial_number="SN-1", work_order_id=order.id),
        ]
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_unit_completion_time_is_recorded_when_it_passes(session):
    order = add_work_order(session, add_product(session))
    unit = Unit(serial_number="SN-1", work_order_id=order.id)
    unit.change_status(UnitStatus.IN_PROCESS)
    assert unit.completed_at is None
    unit.change_status(UnitStatus.PASSED)
    assert unit.completed_at is not None


def test_passed_unit_cannot_change_again():
    unit = Unit(serial_number="SN-1", work_order_id=1, status=UnitStatus.PASSED)
    with pytest.raises(InvalidTransitionError):
        unit.change_status(UnitStatus.FAILED)


# ---------------------------------------------------------------------------------------------
# Traceability
# ---------------------------------------------------------------------------------------------
def test_execution_records_build_the_unit_history(session):
    product, station = add_product(session), add_station(session)
    recipe = add_recipe_with_steps(session, product, station)
    order = add_work_order(session, product)
    unit = Unit(serial_number="SN-1", work_order_id=order.id)
    operator = User(username="op1", full_name="Operator", password_hash="x", role=Role.OPERATOR)
    session.add_all([unit, operator])
    session.commit()

    start = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
    for offset, (step, result, torque) in enumerate(
        [(recipe.steps[0], StepResult.NOK, 8.1), (recipe.steps[0], StepResult.OK, 6.2)]
    ):
        session.add(
            ExecutionRecord(
                unit_id=unit.id,
                recipe_step_id=step.id,
                station_id=station.id,
                operator_id=operator.id,
                result=result,
                measured_values={"torque": torque},
                started_at=start + timedelta(minutes=offset),
                finished_at=start + timedelta(minutes=offset, seconds=20),
            )
        )
    session.commit()
    session.expire_all()

    history = session.get(Unit, unit.id).executions
    assert [record.result for record in history] == [StepResult.NOK, StepResult.OK]
    assert history[1].measured_values == {"torque": 6.2}
    assert history[0].operator.username == "op1"
    assert history[0].recipe_step.name == "Step 1"


# ---------------------------------------------------------------------------------------------
# Downtime
# ---------------------------------------------------------------------------------------------
def test_downtime_event_is_open_until_closed(session):
    event = DowntimeEvent(station_id=add_station(session).id)
    session.add(event)
    session.commit()
    assert event.is_open
    assert event.duration is None


def test_closing_downtime_computes_duration(session):
    start = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    event = DowntimeEvent(station_id=add_station(session).id, started_at=start)
    session.add(event)
    session.commit()
    session.expire_all()

    stored = session.get(DowntimeEvent, event.id)
    stored.close(start + timedelta(minutes=12))
    session.commit()
    assert not stored.is_open
    assert stored.duration == timedelta(minutes=12)


def test_downtime_cannot_end_before_it_starts():
    start = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    event = DowntimeEvent(station_id=1, started_at=start)
    with pytest.raises(ValueError, match="before"):
        event.close(start - timedelta(seconds=1))


def test_downtime_cannot_be_closed_twice():
    event = DowntimeEvent(station_id=1)
    event.close()
    with pytest.raises(ValueError, match="already closed"):
        event.close()


def test_downtime_reason_can_be_assigned_later(session):
    station = add_station(session)
    reason = DowntimeReason(code="NO_MATERIAL", description="Waiting for material")
    event = DowntimeEvent(station_id=station.id)
    session.add_all([reason, event])
    session.commit()

    event.reason_id = reason.id
    session.commit()
    session.expire_all()
    assert session.get(DowntimeEvent, event.id).reason.code == "NO_MATERIAL"


# ---------------------------------------------------------------------------------------------
# Storage format
# ---------------------------------------------------------------------------------------------
def test_enumerations_are_stored_by_value(session):
    session.add(User(username="eng", full_name="Engineer", password_hash="x", role=Role.ADMIN))
    session.commit()
    stored = session.exec(text("SELECT role FROM users WHERE username = 'eng'")).scalar_one()
    assert stored == "admin"


def test_unknown_enumeration_value_is_rejected(session):
    session.add(User(username="bad", full_name="Bad", password_hash="x", role="superuser"))
    with pytest.raises(StatementError):
        session.commit()


def test_timestamps_are_returned_as_utc(session):
    product = add_product(session)
    session.expire_all()
    created_at = session.get(Product, product.id).created_at
    assert created_at.tzinfo is not None
    assert created_at.utcoffset() == timedelta(0)
