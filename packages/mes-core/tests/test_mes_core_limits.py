import pytest

from mes_core.enums import StepResult
from mes_core.limits import ParameterLimit, evaluate_all


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (4.9, StepResult.NOK),
        (5.0, StepResult.OK),
        (6.0, StepResult.OK),
        (7.0, StepResult.OK),
        (7.1, StepResult.NOK),
    ],
)
def test_bounds_are_inclusive(value, expected):
    limit = ParameterLimit("torque", minimum=5.0, maximum=7.0)
    assert limit.evaluate(value) is expected


def test_only_minimum_is_checked_when_maximum_is_missing():
    limit = ParameterLimit("pressure", minimum=2.0)
    assert limit.evaluate(1_000_000) is StepResult.OK
    assert limit.evaluate(1.9) is StepResult.NOK


def test_only_maximum_is_checked_when_minimum_is_missing():
    limit = ParameterLimit("leak_rate", maximum=0.5)
    assert limit.evaluate(-10) is StepResult.OK
    assert limit.evaluate(0.6) is StepResult.NOK


def test_limit_without_bounds_always_passes():
    assert ParameterLimit("note").evaluate(123) is StepResult.OK


def test_inverted_bounds_are_rejected():
    with pytest.raises(ValueError, match="minimum"):
        ParameterLimit("torque", minimum=8.0, maximum=7.0)


def test_blank_name_is_rejected():
    with pytest.raises(ValueError, match="blank"):
        ParameterLimit("  ")


def test_limit_is_immutable():
    limit = ParameterLimit("torque", minimum=5.0)
    with pytest.raises(AttributeError):
        limit.minimum = 1.0


LIMITS = [
    ParameterLimit("torque", minimum=5.0, maximum=7.0),
    ParameterLimit("angle", minimum=30.0, maximum=60.0),
]


def test_evaluate_all_is_ok_when_every_parameter_is_in_range():
    assert evaluate_all(LIMITS, {"torque": 6.0, "angle": 45.0}) is StepResult.OK


def test_evaluate_all_is_nok_when_any_parameter_is_out_of_range():
    assert evaluate_all(LIMITS, {"torque": 6.0, "angle": 70.0}) is StepResult.NOK


def test_evaluate_all_is_nok_when_a_declared_parameter_is_missing():
    assert evaluate_all(LIMITS, {"torque": 6.0}) is StepResult.NOK


def test_evaluate_all_ignores_extra_measurements():
    assert evaluate_all(LIMITS, {"torque": 6.0, "angle": 45.0, "temp": 99}) is StepResult.OK


def test_evaluate_all_without_limits_is_ok():
    assert evaluate_all([], {}) is StepResult.OK
