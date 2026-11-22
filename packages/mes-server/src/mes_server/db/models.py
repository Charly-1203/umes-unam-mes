"""Persistent data model of the MES.

The model is deliberately generic: it describes *what* is produced, *where*, *how* and *what
actually happened*, without assuming a particular process. See ``docs/modelo-de-datos.md`` for
the entity-relationship diagram.

Integrity rules that the database can enforce (uniqueness, foreign keys, positive quantities)
are declared as constraints. Lifecycle rules (which status may follow which) live in
:mod:`mes_core.lifecycle` and are applied through the ``change_status`` methods.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Column, MetaData, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from mes_core.clock import utc_now
from mes_core.enums import RecipeStatus, Role, StepResult, UnitStatus, WorkOrderStatus
from mes_core.lifecycle import (
    RECIPE_TRANSITIONS,
    UNIT_TRANSITIONS,
    WORK_ORDER_TRANSITIONS,
    ensure_transition,
)
from mes_core.limits import ParameterLimit
from mes_server.db.types import UTCDateTime, enum_type

# Deterministic constraint names keep migrations portable, in particular on SQLite where
# Alembic must recreate tables to change a constraint.
SQLModel.metadata.naming_convention = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
).naming_convention


def _json_column() -> Column[Any]:
    return Column(JSON, nullable=False)


# ---------------------------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------------------------
class User(SQLModel, table=True):
    """Person who signs in to the MES.

    Attributes:
        username: Unique sign-in name.
        full_name: Name shown on screens and in traceability records.
        password_hash: Hash of the password; the clear-text password is never stored.
        role: Permission level.
        is_active: Inactive users cannot sign in but remain in historical records.
    """

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(max_length=64, unique=True, index=True)
    full_name: str = Field(max_length=128)
    password_hash: str = Field(max_length=255)
    role: Role = Field(sa_type=enum_type(Role))
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)


# ---------------------------------------------------------------------------------------------
# Product definition
# ---------------------------------------------------------------------------------------------
class Product(SQLModel, table=True):
    """Something the plant produces.

    Attributes:
        code: Unique product code, as known by the ERP.
        name: Human-readable name.
        description: Optional free text.
        is_active: Inactive products cannot receive new work orders.
    """

    __tablename__ = "products"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(max_length=64, unique=True, index=True)
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=512)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)

    bom_items: list["BomItem"] = Relationship(
        back_populates="product",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    recipes: list["Recipe"] = Relationship(back_populates="product")


class BomItem(SQLModel, table=True):
    """One line of a product's bill of materials.

    Attributes:
        component_code: Code of the component, as known by the ERP.
        description: Optional component description.
        quantity: Amount of the component per unit of product; must be positive.
        unit_of_measure: Unit of ``quantity``, for example ``"pcs"`` or ``"kg"``.
    """

    __tablename__ = "bom_items"
    __table_args__ = (
        UniqueConstraint("product_id", "component_code"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", ondelete="CASCADE", index=True)
    component_code: str = Field(max_length=64)
    description: str | None = Field(default=None, max_length=256)
    quantity: float
    unit_of_measure: str = Field(default="pcs", max_length=16)

    product: Product = Relationship(back_populates="bom_items")


# ---------------------------------------------------------------------------------------------
# Shop floor
# ---------------------------------------------------------------------------------------------
class Station(SQLModel, table=True):
    """Workstation where recipe steps are executed. Each one runs its own gateway.

    Attributes:
        code: Unique station code, also used to address the station's gateway.
        name: Human-readable name.
        description: Optional free text.
        is_active: Inactive stations receive no work.
    """

    __tablename__ = "stations"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=512)
    is_active: bool = True


# ---------------------------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------------------------
class Recipe(SQLModel, table=True):
    """Versioned definition of how a product is made.

    A recipe is an ordered list of steps; the order of the steps is also the route through the
    stations. Only released recipes can be used by work orders, and a released recipe is never
    edited: changes create a new version.

    Attributes:
        version: Version number, unique per product, starting at 1.
        status: Lifecycle status.
        released_at: When the recipe was released.
    """

    __tablename__ = "recipes"
    __table_args__ = (
        UniqueConstraint("product_id", "version"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    version: int = 1
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=512)
    status: RecipeStatus = Field(default=RecipeStatus.DRAFT, sa_type=enum_type(RecipeStatus))
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)
    released_at: datetime | None = Field(default=None, sa_type=UTCDateTime)

    product: Product = Relationship(back_populates="recipes")
    steps: list["RecipeStep"] = Relationship(
        back_populates="recipe",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "RecipeStep.sequence",
        },
    )

    def change_status(self, target: RecipeStatus) -> None:
        """Move the recipe to a new status.

        Args:
            target: Requested status.

        Raises:
            mes_core.lifecycle.InvalidTransitionError: If the lifecycle forbids the change.
            ValueError: If a recipe without steps is released.
        """
        ensure_transition(RECIPE_TRANSITIONS, self.status, target)
        if target is RecipeStatus.RELEASED:
            if not self.steps:
                raise ValueError("A recipe must have at least one step to be released.")
            self.released_at = utc_now()
        self.status = target


class RecipeStep(SQLModel, table=True):
    """One step of a recipe, executed at one station.

    Attributes:
        sequence: Position of the step in the recipe, unique within it, starting at 1.
        operation: Code of the operation the station performs, for example ``"SCREW"``.
            The gateway uses it to choose what to ask the PLC to do.
        name: Human-readable name shown to the operator.
        parameters: Parameter definitions with their acceptance limits, as a list of objects
            with the keys ``name``, ``minimum``, ``maximum``, ``nominal`` and ``unit``.
        requires_previous_ok: Interlock flag. When set, a unit may only start this step if
            every previous step of the recipe finished OK for it.
    """

    __tablename__ = "recipe_steps"
    __table_args__ = (
        UniqueConstraint("recipe_id", "sequence"),
        CheckConstraint("sequence >= 1", name="sequence_positive"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipes.id", ondelete="CASCADE", index=True)
    sequence: int
    station_id: int = Field(foreign_key="stations.id", index=True)
    operation: str = Field(max_length=64)
    name: str = Field(max_length=128)
    parameters: list[dict[str, Any]] = Field(default_factory=list, sa_column=_json_column())
    requires_previous_ok: bool = False

    recipe: Recipe = Relationship(back_populates="steps")
    station: Station = Relationship()

    def limits(self) -> list[ParameterLimit]:
        """Return the step's parameters as validated limit objects.

        Returns:
            One :class:`~mes_core.limits.ParameterLimit` per declared parameter.

        Raises:
            ValueError: If a stored parameter definition is invalid.
            TypeError: If a stored parameter has unknown keys.
        """
        return [ParameterLimit(**definition) for definition in self.parameters]


# ---------------------------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------------------------
class WorkOrder(SQLModel, table=True):
    """Request to produce a quantity of a product.

    Attributes:
        order_number: Unique order identifier, as issued by the ERP.
        quantity: Units to produce; must be positive.
        recipe_id: Recipe version used to produce; assigned when the order is released.
        status: Lifecycle status.
    """

    __tablename__ = "work_orders"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    id: int | None = Field(default=None, primary_key=True)
    order_number: str = Field(max_length=64, unique=True, index=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    recipe_id: int | None = Field(default=None, foreign_key="recipes.id")
    quantity: int
    status: WorkOrderStatus = Field(
        default=WorkOrderStatus.CREATED, sa_type=enum_type(WorkOrderStatus)
    )
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)
    released_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    started_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    completed_at: datetime | None = Field(default=None, sa_type=UTCDateTime)

    product: Product = Relationship()
    recipe: Recipe | None = Relationship()
    units: list["Unit"] = Relationship(back_populates="work_order")

    def change_status(self, target: WorkOrderStatus) -> None:
        """Move the order to a new status and record when it happened.

        Args:
            target: Requested status.

        Raises:
            mes_core.lifecycle.InvalidTransitionError: If the lifecycle forbids the change.
        """
        ensure_transition(WORK_ORDER_TRANSITIONS, self.status, target)
        now = utc_now()
        if target is WorkOrderStatus.RELEASED:
            self.released_at = now
        elif target is WorkOrderStatus.IN_PROGRESS and self.started_at is None:
            self.started_at = now
        elif target is WorkOrderStatus.COMPLETED:
            self.completed_at = now
        self.status = target


class Unit(SQLModel, table=True):
    """Individual, serialized item produced by a work order.

    Attributes:
        serial_number: Unique identifier of the item.
        status: Lifecycle status.
        completed_at: When the unit passed or was scrapped.
    """

    __tablename__ = "units"

    id: int | None = Field(default=None, primary_key=True)
    serial_number: str = Field(max_length=64, unique=True, index=True)
    work_order_id: int = Field(foreign_key="work_orders.id", index=True)
    status: UnitStatus = Field(default=UnitStatus.CREATED, sa_type=enum_type(UnitStatus))
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)
    completed_at: datetime | None = Field(default=None, sa_type=UTCDateTime)

    work_order: WorkOrder = Relationship(back_populates="units")
    executions: list["ExecutionRecord"] = Relationship(
        back_populates="unit",
        sa_relationship_kwargs={"order_by": "ExecutionRecord.started_at"},
    )

    def change_status(self, target: UnitStatus) -> None:
        """Move the unit to a new status and record when it finished.

        Args:
            target: Requested status.

        Raises:
            mes_core.lifecycle.InvalidTransitionError: If the lifecycle forbids the change.
        """
        ensure_transition(UNIT_TRANSITIONS, self.status, target)
        if target in (UnitStatus.PASSED, UnitStatus.SCRAPPED):
            self.completed_at = utc_now()
        self.status = target


class ExecutionRecord(SQLModel, table=True):
    """What happened when one recipe step was executed on one unit.

    This is the core of traceability: every execution is recorded, including repeated attempts,
    and records are never modified afterwards.

    Attributes:
        result: OK or NOK.
        measured_values: Measured values keyed by parameter name.
        operator_id: User working at the station, if known.
    """

    __tablename__ = "execution_records"

    id: int | None = Field(default=None, primary_key=True)
    unit_id: int = Field(foreign_key="units.id", index=True)
    recipe_step_id: int = Field(foreign_key="recipe_steps.id", index=True)
    station_id: int = Field(foreign_key="stations.id", index=True)
    operator_id: int | None = Field(default=None, foreign_key="users.id")
    result: StepResult = Field(sa_type=enum_type(StepResult))
    measured_values: dict[str, Any] = Field(default_factory=dict, sa_column=_json_column())
    started_at: datetime = Field(sa_type=UTCDateTime)
    finished_at: datetime = Field(sa_type=UTCDateTime)

    unit: Unit = Relationship(back_populates="executions")
    recipe_step: RecipeStep = Relationship()
    station: Station = Relationship()
    operator: User | None = Relationship()


# ---------------------------------------------------------------------------------------------
# Downtime
# ---------------------------------------------------------------------------------------------
class DowntimeReason(SQLModel, table=True):
    """Catalog entry explaining why a station stopped.

    Attributes:
        code: Unique short code, for example ``"NO_MATERIAL"``.
        description: Text shown to the operator.
        is_active: Inactive reasons cannot be selected for new events.
    """

    __tablename__ = "downtime_reasons"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    description: str = Field(max_length=256)
    is_active: bool = True


class DowntimeEvent(SQLModel, table=True):
    """Period during which a station was not producing.

    An event is opened when the stop is detected and closed when production resumes. The reason
    may be assigned later by the operator.

    Attributes:
        started_at: When the stop began.
        ended_at: When production resumed; empty while the stop is ongoing.
        reason_id: Reason chosen from the catalog, if already known.
        comment: Optional free text.
    """

    __tablename__ = "downtime_events"

    id: int | None = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id", index=True)
    reason_id: int | None = Field(default=None, foreign_key="downtime_reasons.id")
    reported_by_id: int | None = Field(default=None, foreign_key="users.id")
    started_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)
    ended_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    comment: str | None = Field(default=None, max_length=512)

    station: Station = Relationship()
    reason: DowntimeReason | None = Relationship()
    reported_by: User | None = Relationship()

    @property
    def is_open(self) -> bool:
        """Whether the stop is still ongoing."""
        return self.ended_at is None

    @property
    def duration(self) -> timedelta | None:
        """Length of the stop, or ``None`` while it is ongoing."""
        if self.ended_at is None:
            return None
        return self.ended_at - self.started_at

    def close(self, ended_at: datetime | None = None) -> None:
        """Mark the stop as finished.

        Args:
            ended_at: When production resumed. ``None`` uses the current time.

        Raises:
            ValueError: If the event is already closed or the end precedes the start.
        """
        if not self.is_open:
            raise ValueError("Downtime event is already closed.")
        end = ended_at or utc_now()
        if end < self.started_at:
            raise ValueError("Downtime cannot end before it starts.")
        self.ended_at = end


# ---------------------------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------------------------
class AuditEntry(SQLModel, table=True):
    """Record of an administrative action, such as a backup or a course reset.

    The actor is stored as text, not as a reference to ``users``, so the entry survives when
    the user is deleted. Entries are never modified and are kept by every course reset.

    Attributes:
        actor: Username of who performed the action, or ``"terminal"`` for the command line.
        action: Stable action identifier, such as ``"course_reset"``.
        detail: Additional data about the action.
    """

    __tablename__ = "audit_entries"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime, index=True)
    actor: str = Field(max_length=64)
    action: str = Field(max_length=64, index=True)
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=_json_column())


__all__ = [
    "AuditEntry",
    "BomItem",
    "DowntimeEvent",
    "DowntimeReason",
    "ExecutionRecord",
    "Product",
    "Recipe",
    "RecipeStep",
    "Station",
    "Unit",
    "User",
    "WorkOrder",
]
