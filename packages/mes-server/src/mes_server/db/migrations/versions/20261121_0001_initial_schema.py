"""Initial schema: users, product definition, stations, recipes, production and downtime.

Revision ID: 0001
Revises:
Create Date: 2026-11-21 19:29:29.845079
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

import mes_server.db.types

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table(
        "downtime_reasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_downtime_reasons")),
    )
    with op.batch_alter_table("downtime_reasons", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_downtime_reasons_code"), ["code"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
    )
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_products_code"), ["code"], unique=True)

    op.create_table(
        "stations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stations")),
    )
    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_stations_code"), ["code"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("full_name", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "admin",
                "process_engineer",
                "supervisor",
                "operator",
                name="role",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_users_username"), ["username"], unique=True)

    op.create_table(
        "bom_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("component_code", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit_of_measure", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_bom_items_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_bom_items_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bom_items")),
        sa.UniqueConstraint(
            "product_id", "component_code", name=op.f("uq_bom_items_product_id_component_code")
        ),
    )
    with op.batch_alter_table("bom_items", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_bom_items_product_id"), ["product_id"], unique=False)

    op.create_table(
        "downtime_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("reason_id", sa.Integer(), nullable=True),
        sa.Column("reported_by_id", sa.Integer(), nullable=True),
        sa.Column("started_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("ended_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("comment", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["reason_id"],
            ["downtime_reasons.id"],
            name=op.f("fk_downtime_events_reason_id_downtime_reasons"),
        ),
        sa.ForeignKeyConstraint(
            ["reported_by_id"], ["users.id"], name=op.f("fk_downtime_events_reported_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["stations.id"], name=op.f("fk_downtime_events_station_id_stations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_downtime_events")),
    )
    with op.batch_alter_table("downtime_events", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_downtime_events_station_id"), ["station_id"], unique=False
        )

    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "released", "obsolete", name="recipestatus", native_enum=False, length=32
            ),
            nullable=False,
        ),
        sa.Column("created_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("released_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version >= 1", name=op.f("ck_recipes_version_positive")),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_recipes_product_id_products")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipes")),
        sa.UniqueConstraint("product_id", "version", name=op.f("uq_recipes_product_id_version")),
    )
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_recipes_product_id"), ["product_id"], unique=False)

    op.create_table(
        "recipe_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("operation", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("requires_previous_ok", sa.Boolean(), nullable=False),
        sa.CheckConstraint("sequence >= 1", name=op.f("ck_recipe_steps_sequence_positive")),
        sa.ForeignKeyConstraint(
            ["recipe_id"],
            ["recipes.id"],
            name=op.f("fk_recipe_steps_recipe_id_recipes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["stations.id"], name=op.f("fk_recipe_steps_station_id_stations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe_steps")),
        sa.UniqueConstraint(
            "recipe_id", "sequence", name=op.f("uq_recipe_steps_recipe_id_sequence")
        ),
    )
    with op.batch_alter_table("recipe_steps", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_recipe_steps_recipe_id"), ["recipe_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_recipe_steps_station_id"), ["station_id"], unique=False
        )

    op.create_table(
        "work_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_number", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "created",
                "released",
                "in_progress",
                "paused",
                "completed",
                "closed",
                "cancelled",
                name="workorderstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("created_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("released_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("started_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("completed_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=True),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_work_orders_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_work_orders_product_id_products")
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"], ["recipes.id"], name=op.f("fk_work_orders_recipe_id_recipes")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_orders")),
    )
    with op.batch_alter_table("work_orders", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_work_orders_order_number"), ["order_number"], unique=True
        )
        batch_op.create_index(batch_op.f("ix_work_orders_product_id"), ["product_id"], unique=False)

    op.create_table(
        "units",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("serial_number", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "created",
                "in_process",
                "passed",
                "failed",
                "scrapped",
                name="unitstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("created_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("completed_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["work_order_id"], ["work_orders.id"], name=op.f("fk_units_work_order_id_work_orders")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_units")),
    )
    with op.batch_alter_table("units", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_units_serial_number"), ["serial_number"], unique=True)
        batch_op.create_index(batch_op.f("ix_units_work_order_id"), ["work_order_id"], unique=False)

    op.create_table(
        "execution_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("recipe_step_id", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column(
            "result",
            sa.Enum("ok", "nok", name="stepresult", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("measured_values", sa.JSON(), nullable=False),
        sa.Column("started_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("finished_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["operator_id"], ["users.id"], name=op.f("fk_execution_records_operator_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["recipe_step_id"],
            ["recipe_steps.id"],
            name=op.f("fk_execution_records_recipe_step_id_recipe_steps"),
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["stations.id"], name=op.f("fk_execution_records_station_id_stations")
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["units.id"], name=op.f("fk_execution_records_unit_id_units")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execution_records")),
    )
    with op.batch_alter_table("execution_records", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_execution_records_recipe_step_id"), ["recipe_step_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_execution_records_station_id"), ["station_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_execution_records_unit_id"), ["unit_id"], unique=False)


def downgrade() -> None:
    """Revert this migration."""
    with op.batch_alter_table("execution_records", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_execution_records_unit_id"))
        batch_op.drop_index(batch_op.f("ix_execution_records_station_id"))
        batch_op.drop_index(batch_op.f("ix_execution_records_recipe_step_id"))

    op.drop_table("execution_records")
    with op.batch_alter_table("units", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_units_work_order_id"))
        batch_op.drop_index(batch_op.f("ix_units_serial_number"))

    op.drop_table("units")
    with op.batch_alter_table("work_orders", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_work_orders_product_id"))
        batch_op.drop_index(batch_op.f("ix_work_orders_order_number"))

    op.drop_table("work_orders")
    with op.batch_alter_table("recipe_steps", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_recipe_steps_station_id"))
        batch_op.drop_index(batch_op.f("ix_recipe_steps_recipe_id"))

    op.drop_table("recipe_steps")
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_recipes_product_id"))

    op.drop_table("recipes")
    with op.batch_alter_table("downtime_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_downtime_events_station_id"))

    op.drop_table("downtime_events")
    with op.batch_alter_table("bom_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_bom_items_product_id"))

    op.drop_table("bom_items")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_username"))

    op.drop_table("users")
    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stations_code"))

    op.drop_table("stations")
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_products_code"))

    op.drop_table("products")
    with op.batch_alter_table("downtime_reasons", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_downtime_reasons_code"))

    op.drop_table("downtime_reasons")
