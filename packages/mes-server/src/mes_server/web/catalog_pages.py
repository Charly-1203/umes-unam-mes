"""Catalog screens: products (with their bill of materials), stations and downtime reasons.

The three catalogs share one screen, :func:`catalog_page`, configured by a
:class:`CatalogSpec`. Each spec says which columns to show, which fields the forms have and
which services to call; the rules (who may deactivate, who may delete) are the same for all.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nicegui import ui
from sqlalchemy import Engine
from sqlmodel import Session

from mes_core.enums import Role
from mes_core.permissions import Permission, has_permission
from mes_server.db.engine import session_scope
from mes_server.db.models import User
from mes_server.services import downtime_reasons, products, stations
from mes_server.services.errors import NotFoundError
from mes_server.web.components import (
    Column,
    Field,
    confirm_dialog,
    data_table,
    form_dialog,
    icon_button,
    info_dialog,
    page_header,
    status_chip,
)
from mes_server.web.messages import describe_usage

Row = dict[str, Any]

CODE_HINT = "Letras, números, punto, guion o guion bajo. No se puede cambiar después."


@dataclass(frozen=True, slots=True)
class CatalogSpec:
    """Configuration of one catalog screen.

    Attributes:
        title: Screen title, in plural (``"Productos"``).
        subtitle: One-line explanation under the title.
        singular: Name of one record with its article, for messages (``"el producto"``).
        new_label: Text of the button that creates a record.
        empty_text: Message shown when there are no records.
        columns: Columns of the table, besides the state and the actions.
        create_fields: Inputs of the creation form.
        edit_fields: Inputs of the edit form; the code is shown read-only.
        list_rows: Returns the table rows; receives a session and whether to include
            inactive records.
        create: Creates a record from the form values.
        update: Updates a record from its id and the form values.
        set_active: Activates or deactivates a record.
        usage: Counts the records that reference one.
        delete: Deletes a record; receives the id and the role of the user.
        detail_path: Builds the URL of a record's detail screen, when it has one.
        detail_tooltip: Text of the button that opens the detail screen.
    """

    title: str
    subtitle: str
    singular: str
    new_label: str
    empty_text: str
    columns: tuple[Column, ...]
    create_fields: tuple[Field, ...]
    edit_fields: tuple[Field, ...]
    list_rows: Callable[[Session, bool], list[Row]]
    create: Callable[[Session, dict[str, Any]], Any]
    update: Callable[[Session, int, dict[str, Any]], Any]
    set_active: Callable[[Session, int, bool], Any]
    usage: Callable[[Session, int], dict[str, int]]
    delete: Callable[[Session, int, Role], None]
    detail_path: Callable[[Row], str] | None = None
    detail_tooltip: str = "Ver detalle"


def _code_cell(row: Row) -> None:
    ui.label(row["code"]).classes("mes-cell-code")


def _status_cell(row: Row) -> None:
    status_chip(row["is_active"])


STATUS_COLUMN = Column("Estado", "is_active", render=_status_cell)


# ---------------------------------------------------------------------------------------------
# Generic catalog screen
# ---------------------------------------------------------------------------------------------
def catalog_page(engine: Engine, user: User, spec: CatalogSpec) -> None:
    """Build a catalog screen: table, filters and the create, edit, (de)activate and delete flows.

    Args:
        engine: Database engine.
        user: Signed-in user; only administrators see the delete button.
        spec: What the screen shows and which services it calls.
    """
    can_delete = has_permission(user.role, Permission.ADMINISTER_SYSTEM)
    state = {"show_inactive": False}

    def apply(action: Callable[[Session], Any], message: str) -> None:
        with session_scope(engine) as session:
            action(session)
        table.refresh()
        ui.notify(message, type="positive")

    def open_create() -> None:
        form_dialog(
            spec.new_label,
            spec.create_fields,
            lambda values: apply(lambda s: spec.create(s, values), "Registro creado."),
        )

    def open_edit(row: Row) -> None:
        form_dialog(
            f"Editar {row['code']}",
            spec.edit_fields,
            lambda values: apply(lambda s: spec.update(s, row["id"], values), "Cambios guardados."),
            initial=row,
        )

    def toggle_active(row: Row) -> None:
        if row["is_active"]:
            confirm_dialog(
                f"Desactivar {row['code']}",
                f"No se podrá usar {spec.singular} en trabajos nuevos. Su historia se conserva "
                "y puedes volver a activarlo cuando quieras.",
                lambda: apply(lambda s: spec.set_active(s, row["id"], False), "Desactivado."),
                confirm_label="Desactivar",
            )
        else:
            apply(lambda s: spec.set_active(s, row["id"], True), "Activado.")

    def start_delete(row: Row) -> None:
        with Session(engine) as session:
            usage = spec.usage(session, row["id"])
        if usage:
            info_dialog(
                f"No se puede borrar {row['code']}",
                f"Tiene {describe_usage(usage)}. Puedes desactivarlo para que no se use en "
                "trabajos nuevos; su historia se limpia con el reinicio de curso.",
            )
            return
        confirm_dialog(
            f"Borrar {row['code']}",
            f"Se borrará {spec.singular} de forma permanente. Esta acción no se puede deshacer.",
            lambda: apply(lambda s: spec.delete(s, row["id"], user.role), "Registro borrado."),
            confirm_label="Borrar",
            danger=True,
        )

    def row_actions(row: Row) -> None:
        code = row["code"]
        if spec.detail_path:
            path = spec.detail_path(row)
            icon_button(
                "list_alt",
                spec.detail_tooltip,
                lambda: ui.navigate.to(path),
                marker=f"detail-{code}",
            )
        icon_button("edit", "Editar", lambda: open_edit(row), marker=f"edit-{code}")
        if row["is_active"]:
            icon_button(
                "block", "Desactivar", lambda: toggle_active(row), marker=f"deactivate-{code}"
            )
        else:
            icon_button(
                "check_circle", "Activar", lambda: toggle_active(row), marker=f"activate-{code}"
            )
        if can_delete:
            icon_button(
                "delete",
                "Borrar",
                lambda: start_delete(row),
                marker=f"delete-{code}",
                danger=True,
            )

    with page_header(spec.title, spec.subtitle):
        ui.button(spec.new_label, icon="add", on_click=open_create).props(
            "unelevated no-caps"
        ).mark("catalog-new")

    with ui.element("div").classes("mes-panel"):
        with ui.element("div").classes("mes-toolbar"):
            ui.switch(
                "Mostrar inactivos",
                on_change=lambda e: (state.update(show_inactive=e.value), table.refresh()),
            ).mark("show-inactive")

        @ui.refreshable
        def table() -> None:
            with Session(engine) as session:
                rows = spec.list_rows(session, state["show_inactive"])
            data_table(
                (*spec.columns, STATUS_COLUMN),
                rows,
                actions=row_actions,
                empty_text=spec.empty_text,
            )

        table()


# ---------------------------------------------------------------------------------------------
# Catalog configurations
# ---------------------------------------------------------------------------------------------
def _product_rows(session: Session, include_inactive: bool) -> list[Row]:
    return [
        {
            "id": product.id,
            "code": product.code,
            "name": product.name,
            "description": product.description,
            "is_active": product.is_active,
            "bom_count": len(product.bom_items),
        }
        for product in products.list_products(session, include_inactive=include_inactive)
    ]


def _station_rows(session: Session, include_inactive: bool) -> list[Row]:
    return [
        {
            "id": station.id,
            "code": station.code,
            "name": station.name,
            "description": station.description,
            "is_active": station.is_active,
        }
        for station in stations.list_stations(session, include_inactive=include_inactive)
    ]


def _reason_rows(session: Session, include_inactive: bool) -> list[Row]:
    return [
        {
            "id": reason.id,
            "code": reason.code,
            "description": reason.description,
            "is_active": reason.is_active,
        }
        for reason in downtime_reasons.list_reasons(session, include_inactive=include_inactive)
    ]


PRODUCTS = CatalogSpec(
    title="Productos",
    subtitle="Lo que se fabrica en la línea y su lista de materiales.",
    singular="el producto",
    new_label="Nuevo producto",
    empty_text="Aún no hay productos. Crea el primero con «Nuevo producto».",
    columns=(
        Column("Código", "code", render=_code_cell),
        Column("Nombre", "name"),
        Column("Componentes", "bom_count", css="mes-cell-number"),
    ),
    create_fields=(
        Field("code", "Código", hint=CODE_HINT),
        Field("name", "Nombre"),
        Field("description", "Descripción", kind="textarea"),
    ),
    edit_fields=(
        Field("code", "Código", read_only=True),
        Field("name", "Nombre"),
        Field("description", "Descripción", kind="textarea"),
    ),
    list_rows=_product_rows,
    create=lambda s, v: products.create_product(
        s, code=v["code"], name=v["name"], description=v["description"]
    ),
    update=lambda s, i, v: products.update_product(
        s, i, name=v["name"], description=v["description"]
    ),
    set_active=products.set_product_active,
    usage=products.product_usage,
    delete=lambda s, i, role: products.delete_product(s, i, actor_role=role),
    detail_path=lambda row: f"/products/{row['id']}",
    detail_tooltip="Lista de materiales",
)

STATIONS = CatalogSpec(
    title="Estaciones",
    subtitle="Estaciones de trabajo de la línea. Cada una tiene su propio gateway.",
    singular="la estación",
    new_label="Nueva estación",
    empty_text="Aún no hay estaciones. Crea la primera con «Nueva estación».",
    columns=(
        Column("Código", "code", render=_code_cell),
        Column("Nombre", "name"),
        Column("Descripción", "description"),
    ),
    create_fields=(
        Field("code", "Código", hint=CODE_HINT),
        Field("name", "Nombre"),
        Field("description", "Descripción", kind="textarea"),
    ),
    edit_fields=(
        Field("code", "Código", read_only=True),
        Field("name", "Nombre"),
        Field("description", "Descripción", kind="textarea"),
    ),
    list_rows=_station_rows,
    create=lambda s, v: stations.create_station(
        s, code=v["code"], name=v["name"], description=v["description"]
    ),
    update=lambda s, i, v: stations.update_station(
        s, i, name=v["name"], description=v["description"]
    ),
    set_active=stations.set_station_active,
    usage=stations.station_usage,
    delete=lambda s, i, role: stations.delete_station(s, i, actor_role=role),
)

DOWNTIME_REASONS = CatalogSpec(
    title="Motivos de paro",
    subtitle="Causas que el operador elige al explicar por qué se detuvo una estación.",
    singular="el motivo",
    new_label="Nuevo motivo",
    empty_text="Aún no hay motivos de paro. Crea el primero con «Nuevo motivo».",
    columns=(
        Column("Código", "code", render=_code_cell),
        Column("Descripción", "description"),
    ),
    create_fields=(
        Field("code", "Código", hint=CODE_HINT),
        Field("description", "Descripción"),
    ),
    edit_fields=(
        Field("code", "Código", read_only=True),
        Field("description", "Descripción"),
    ),
    list_rows=_reason_rows,
    create=lambda s, v: downtime_reasons.create_reason(
        s, code=v["code"], description=v["description"]
    ),
    update=lambda s, i, v: downtime_reasons.update_reason(s, i, description=v["description"]),
    set_active=downtime_reasons.set_reason_active,
    usage=downtime_reasons.reason_usage,
    delete=lambda s, i, role: downtime_reasons.delete_reason(s, i, actor_role=role),
)


def products_page(engine: Engine, user: User) -> None:
    """Build the products screen.

    Args:
        engine: Database engine.
        user: Signed-in user.
    """
    catalog_page(engine, user, PRODUCTS)


def stations_page(engine: Engine, user: User) -> None:
    """Build the stations screen.

    Args:
        engine: Database engine.
        user: Signed-in user.
    """
    catalog_page(engine, user, STATIONS)


def downtime_reasons_page(engine: Engine, user: User) -> None:
    """Build the downtime reasons screen.

    Args:
        engine: Database engine.
        user: Signed-in user.
    """
    catalog_page(engine, user, DOWNTIME_REASONS)


# ---------------------------------------------------------------------------------------------
# Product detail: bill of materials
# ---------------------------------------------------------------------------------------------
BOM_FIELDS = (
    Field("component_code", "Componente", hint="Código del componente, como lo conoce el ERP."),
    Field("description", "Descripción"),
    Field("quantity", "Cantidad por unidad de producto", kind="number"),
    Field("unit_of_measure", "Unidad", hint="Por ejemplo: pcs, kg, m."),
)


def format_quantity(value: float) -> str:
    """Show a quantity without needless decimals (``4`` instead of ``4.0``).

    Args:
        value: Quantity.

    Returns:
        The formatted quantity.
    """
    return f"{value:g}"


def product_detail_page(engine: Engine, user: User, product_id: str) -> None:
    """Build a product's detail screen with its bill of materials.

    Args:
        engine: Database engine.
        user: Signed-in user.
        product_id: Product id taken from the URL.
    """
    try:
        with Session(engine) as session:
            product = products.get_product(session, int(product_id))
            header = {
                "code": product.code,
                "name": product.name,
                "description": product.description,
                "is_active": product.is_active,
            }
    except (ValueError, NotFoundError):
        with ui.element("div").classes("mes-panel"):
            ui.label("El producto no existe.").classes("mes-empty")
            ui.button("Volver a productos", on_click=lambda: ui.navigate.to("/products")).props(
                "flat no-caps"
            )
        return
    pid = int(product_id)

    def apply(action: Callable[[Session], Any], message: str) -> None:
        with session_scope(engine) as session:
            action(session)
        bom.refresh()
        ui.notify(message, type="positive")

    def open_add() -> None:
        form_dialog(
            "Agregar componente",
            BOM_FIELDS,
            lambda v: apply(
                lambda s: products.add_bom_item(
                    s,
                    pid,
                    component_code=v["component_code"],
                    quantity=v["quantity"],
                    unit_of_measure=v["unit_of_measure"],
                    description=v["description"],
                ),
                "Componente agregado.",
            ),
            initial={"unit_of_measure": "pcs", "quantity": 1},
            save_label="Agregar",
        )

    def open_edit(row: Row) -> None:
        form_dialog(
            f"Editar {row['component_code']}",
            BOM_FIELDS,
            lambda v: apply(
                lambda s: products.update_bom_item(
                    s,
                    row["id"],
                    component_code=v["component_code"],
                    quantity=v["quantity"],
                    unit_of_measure=v["unit_of_measure"],
                    description=v["description"],
                ),
                "Cambios guardados.",
            ),
            initial=row,
        )

    def remove(row: Row) -> None:
        confirm_dialog(
            f"Quitar {row['component_code']}",
            "El componente se quitará de la lista de materiales.",
            lambda: apply(lambda s: products.delete_bom_item(s, row["id"]), "Componente quitado."),
            confirm_label="Quitar",
            danger=True,
        )

    def bom_actions(row: Row) -> None:
        code = row["component_code"]
        icon_button("edit", "Editar", lambda: open_edit(row), marker=f"bom-edit-{code}")
        icon_button(
            "delete", "Quitar", lambda: remove(row), marker=f"bom-delete-{code}", danger=True
        )

    ui.button("Productos", icon="arrow_back", on_click=lambda: ui.navigate.to("/products")).props(
        "flat no-caps dense"
    ).classes("self-start").mark("back-to-products")
    with page_header(f"{header['code']} · {header['name']}", header["description"]):
        status_chip(header["is_active"])

    with ui.element("div").classes("mes-panel"):
        with ui.element("div").classes("mes-toolbar"):
            ui.label("Lista de materiales").classes("mes-panel-title")
            ui.button("Agregar componente", icon="add", on_click=open_add).props(
                "unelevated no-caps"
            ).mark("bom-add")

        @ui.refreshable
        def bom() -> None:
            with Session(engine) as session:
                rows = [
                    {
                        "id": item.id,
                        "component_code": item.component_code,
                        "description": item.description,
                        "quantity": item.quantity,
                        "quantity_text": format_quantity(item.quantity),
                        "unit_of_measure": item.unit_of_measure,
                    }
                    for item in products.list_bom_items(session, pid)
                ]
            data_table(
                (
                    Column(
                        "Componente",
                        "component_code",
                        render=lambda r: ui.label(r["component_code"]).classes("mes-cell-code"),
                    ),
                    Column("Descripción", "description"),
                    Column("Cantidad", "quantity_text", css="mes-cell-number"),
                    Column("Unidad", "unit_of_measure"),
                ),
                rows,
                actions=bom_actions,
                empty_text="Este producto aún no tiene componentes.",
            )

        bom()
