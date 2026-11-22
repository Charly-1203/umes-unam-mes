import pytest

from mes_core.enums import RecipeStatus, UnitStatus, WorkOrderStatus
from mes_core.lifecycle import (
    RECIPE_TRANSITIONS,
    UNIT_TRANSITIONS,
    WORK_ORDER_TRANSITIONS,
    InvalidTransitionError,
    can_transition,
    ensure_transition,
    is_terminal,
)

ALL_TABLES = [
    (WORK_ORDER_TRANSITIONS, WorkOrderStatus),
    (RECIPE_TRANSITIONS, RecipeStatus),
    (UNIT_TRANSITIONS, UnitStatus),
]


@pytest.mark.parametrize(("table", "enum"), ALL_TABLES)
def test_every_status_has_an_entry(table, enum):
    assert set(table) == set(enum)


@pytest.mark.parametrize(("table", "_enum"), ALL_TABLES)
def test_no_status_transitions_to_itself(table, _enum):
    for status, targets in table.items():
        assert status not in targets


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (WorkOrderStatus.CREATED, WorkOrderStatus.RELEASED),
        (WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS),
        (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.PAUSED),
        (WorkOrderStatus.PAUSED, WorkOrderStatus.IN_PROGRESS),
        (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED),
        (WorkOrderStatus.COMPLETED, WorkOrderStatus.CLOSED),
        (WorkOrderStatus.CREATED, WorkOrderStatus.CANCELLED),
    ],
)
def test_work_order_allows_normal_flow(current, target):
    assert can_transition(WORK_ORDER_TRANSITIONS, current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (WorkOrderStatus.CREATED, WorkOrderStatus.IN_PROGRESS),
        (WorkOrderStatus.COMPLETED, WorkOrderStatus.IN_PROGRESS),
        (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED),
        (WorkOrderStatus.CLOSED, WorkOrderStatus.RELEASED),
    ],
)
def test_work_order_rejects_skipped_or_backward_steps(current, target):
    assert not can_transition(WORK_ORDER_TRANSITIONS, current, target)


def test_ensure_transition_returns_target_when_allowed():
    result = ensure_transition(RECIPE_TRANSITIONS, RecipeStatus.DRAFT, RecipeStatus.RELEASED)
    assert result is RecipeStatus.RELEASED


def test_ensure_transition_raises_with_both_statuses_in_message():
    with pytest.raises(InvalidTransitionError) as exc:
        ensure_transition(RECIPE_TRANSITIONS, RecipeStatus.OBSOLETE, RecipeStatus.DRAFT)
    assert exc.value.current == "obsolete"
    assert exc.value.target == "draft"
    assert "obsolete" in str(exc.value)
    assert "draft" in str(exc.value)


def test_failed_unit_can_be_reworked():
    assert can_transition(UNIT_TRANSITIONS, UnitStatus.FAILED, UnitStatus.IN_PROCESS)


@pytest.mark.parametrize(
    ("table", "status", "expected"),
    [
        (WORK_ORDER_TRANSITIONS, WorkOrderStatus.CLOSED, True),
        (WORK_ORDER_TRANSITIONS, WorkOrderStatus.CANCELLED, True),
        (WORK_ORDER_TRANSITIONS, WorkOrderStatus.RELEASED, False),
        (RECIPE_TRANSITIONS, RecipeStatus.OBSOLETE, True),
        (UNIT_TRANSITIONS, UnitStatus.PASSED, True),
        (UNIT_TRANSITIONS, UnitStatus.FAILED, False),
    ],
)
def test_is_terminal(table, status, expected):
    assert is_terminal(table, status) is expected
