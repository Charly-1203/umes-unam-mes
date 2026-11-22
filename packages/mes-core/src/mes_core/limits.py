"""Acceptance limits for measured values.

A recipe step declares the parameters it measures and, for each one, the range that counts as
OK. The same evaluation runs wherever a result is judged, so the server and the gateway always
agree on whether a measurement passed.
"""

from dataclasses import dataclass

from mes_core.enums import StepResult


@dataclass(frozen=True, slots=True)
class ParameterLimit:
    """Acceptance range of one measured parameter.

    Both bounds are inclusive and optional: a missing bound is not checked.

    Attributes:
        name: Parameter identifier, for example ``"torque"``.
        minimum: Lowest accepted value.
        maximum: Highest accepted value.
        nominal: Target value, for reference only.
        unit: Engineering unit, for example ``"N·m"``.
    """

    name: str
    minimum: float | None = None
    maximum: float | None = None
    nominal: float | None = None
    unit: str | None = None

    def __post_init__(self) -> None:
        """Validate the definition.

        Raises:
            ValueError: If the name is blank or the bounds are inverted.
        """
        if not self.name.strip():
            raise ValueError("Parameter name must not be blank.")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(
                f"Parameter '{self.name}': minimum {self.minimum} is greater than "
                f"maximum {self.maximum}."
            )

    def evaluate(self, value: float) -> StepResult:
        """Judge a measured value against the limit.

        Args:
            value: Measured value.

        Returns:
            :attr:`StepResult.OK` when the value is inside the range, otherwise
            :attr:`StepResult.NOK`.
        """
        if self.minimum is not None and value < self.minimum:
            return StepResult.NOK
        if self.maximum is not None and value > self.maximum:
            return StepResult.NOK
        return StepResult.OK


def evaluate_all(limits: list[ParameterLimit], measured: dict[str, float]) -> StepResult:
    """Judge a set of measurements; the step is OK only if every parameter is OK.

    Args:
        limits: Limits declared by the recipe step.
        measured: Measured values keyed by parameter name.

    Returns:
        :attr:`StepResult.OK` when every declared parameter was measured and is in range.
        A declared parameter that is missing from ``measured`` makes the step NOK.
    """
    for limit in limits:
        if limit.name not in measured or limit.evaluate(measured[limit.name]) is StepResult.NOK:
            return StepResult.NOK
    return StepResult.OK
