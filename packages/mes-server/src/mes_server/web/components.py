"""Reusable building blocks for the screens: tables, forms and confirmations.

They keep every screen consistent and keep the screens themselves short. Styles come from the
``mes-*`` classes in ``static/css/theme.css``.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from nicegui import ui

from mes_server.services.errors import ServiceError
from mes_server.web.messages import describe

FieldKind = Literal["text", "textarea", "number"]


# ---------------------------------------------------------------------------------------------
# Page structure
# ---------------------------------------------------------------------------------------------
def page_header(title: str, subtitle: str | None = None) -> ui.row:
    """Show a screen's title and return the row where its main actions go.

    Args:
        title: Screen title.
        subtitle: Optional one-line explanation.

    Returns:
        A row aligned to the right of the title; add buttons inside it with ``with``.
    """
    with ui.element("div").classes("mes-page-header"):
        with ui.column().classes("gap-1"):
            ui.label(title).classes("mes-page-title")
            if subtitle:
                ui.label(subtitle).classes("mes-page-subtitle")
        actions = ui.row().classes("items-center gap-2")
    return actions


def status_chip(active: bool) -> None:
    """Show whether a record is active.

    Args:
        active: State of the record.
    """
    if active:
        ui.label("Activo").classes("mes-chip mes-chip--active")
    else:
        ui.label("Inactivo").classes("mes-chip mes-chip--inactive")


# ---------------------------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Column:
    """One column of a :func:`data_table`.

    Attributes:
        header: Text shown in the header.
        key: Key of the row dictionary that holds the cell value.
        render: Optional function that draws the cell instead of plain text.
        css: Extra classes for the cells, for example ``"mes-cell-code"``.
    """

    header: str
    key: str
    render: Callable[[dict[str, Any]], None] | None = None
    css: str = ""


def data_table(
    columns: Sequence[Column],
    rows: Sequence[dict[str, Any]],
    *,
    actions: Callable[[dict[str, Any]], None] | None = None,
    empty_text: str = "No hay registros.",
) -> None:
    """Draw a table, or a message when there are no rows.

    Args:
        columns: Columns to show.
        rows: One dictionary per row.
        actions: Function that draws the buttons of a row in a last column.
        empty_text: Message shown when ``rows`` is empty.
    """
    if not rows:
        ui.label(empty_text).classes("mes-empty")
        return
    with ui.element("div").classes("mes-table-wrap"), ui.element("table").classes("mes-table"):
        with ui.element("thead"), ui.element("tr"):
            for column in columns:
                with ui.element("th").classes(column.css):
                    ui.label(column.header)
            if actions:
                with ui.element("th").classes("mes-cell-actions"):
                    ui.label("Acciones")
        with ui.element("tbody"):
            for row in rows:
                with ui.element("tr"):
                    for column in columns:
                        with ui.element("td").classes(column.css):
                            if column.render:
                                column.render(row)
                            else:
                                ui.label(cell_text(row.get(column.key)))
                    if actions:
                        with (
                            ui.element("td").classes("mes-cell-actions"),
                            ui.row().classes("gap-1 no-wrap justify-end"),
                        ):
                            actions(row)


def cell_text(value: Any) -> str:
    """Render a cell value as text; missing values show a dash, zero stays zero.

    Args:
        value: Cell value.

    Returns:
        The text to show.
    """
    if value is None or value == "":
        return "—"
    return str(value)


def icon_button(
    icon: str, tooltip: str, on_click: Callable[[], Any], *, marker: str, danger: bool = False
) -> ui.button:
    """Draw a compact icon button with a tooltip and an accessible name.

    Args:
        icon: Material icon name.
        tooltip: Text shown on hover and read by screen readers.
        on_click: Action to run.
        marker: Identifier used by tests to find the button.
        danger: Paint the button in the error color.

    Returns:
        The button.
    """
    color = "negative" if danger else "primary"
    button = (
        ui.button(icon=icon, on_click=on_click)
        .props(f'flat round dense color={color} aria-label="{tooltip}"')
        .tooltip(tooltip)
        .mark(marker)
    )
    return button


# ---------------------------------------------------------------------------------------------
# Forms and confirmations
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Field:
    """One input of a :func:`form_dialog`.

    Attributes:
        name: Key of the value in the dictionary passed to the save function; it must match
            the ``field`` reported by service errors so they appear under this input.
        label: Text shown on the input.
        kind: ``"text"``, ``"textarea"`` or ``"number"``.
        read_only: Show the value but do not allow changing it.
        hint: Help text shown under the input.
    """

    name: str
    label: str
    kind: FieldKind = "text"
    read_only: bool = False
    hint: str | None = None


def form_dialog(
    title: str,
    fields: Sequence[Field],
    on_save: Callable[[dict[str, Any]], None],
    *,
    initial: dict[str, Any] | None = None,
    save_label: str = "Guardar",
) -> ui.dialog:
    """Open a dialog with a form and save it through ``on_save``.

    When ``on_save`` raises a :class:`ServiceError` the dialog stays open and the Spanish
    message appears under the input it refers to (or as a notification when it refers to no
    input). Otherwise the dialog closes.

    Args:
        title: Dialog title.
        fields: Inputs to show, in order.
        on_save: Function that receives the values keyed by field name.
        initial: Starting values keyed by field name.
        save_label: Text of the confirm button.

    Returns:
        The open dialog.
    """
    values = initial or {}
    inputs: dict[str, ui.input | ui.textarea | ui.number] = {}

    with ui.dialog() as dialog, ui.card().classes("mes-dialog"):
        ui.label(title).classes("mes-dialog-title")
        for field in fields:
            value = values.get(field.name)
            if field.kind == "number":
                element = ui.number(field.label, value=value)
            elif field.kind == "textarea":
                element = ui.textarea(field.label, value=value or "").props("autogrow")
            else:
                element = ui.input(field.label, value=value or "")
            element.props("outlined").classes("w-full").mark(f"field-{field.name}")
            if field.read_only:
                element.props("readonly").classes("mes-input-readonly")
            if field.hint:
                element.props(f'hint="{field.hint}"')
            inputs[field.name] = element

        def save() -> None:
            for element in inputs.values():
                element.error = None
            data = {name: element.value for name, element in inputs.items()}
            try:
                on_save(data)
            except ServiceError as error:
                message = describe(error)
                if error.field in inputs:
                    inputs[error.field].error = message
                else:
                    ui.notify(message, type="negative")
                return
            dialog.close()

        with ui.row().classes("w-full justify-end gap-2 pt-2"):
            ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").mark("dialog-cancel")
            ui.button(save_label, on_click=save).props("unelevated no-caps").mark("dialog-save")
    dialog.open()
    return dialog


def confirm_dialog(
    title: str,
    message: str,
    on_confirm: Callable[[], None],
    *,
    confirm_label: str,
    danger: bool = False,
) -> ui.dialog:
    """Ask the user to confirm an action.

    Args:
        title: Dialog title.
        message: What will happen.
        on_confirm: Action to run when confirmed. A :class:`ServiceError` is shown as a
            notification.
        confirm_label: Text of the confirm button.
        danger: Paint the confirm button in the error color.

    Returns:
        The open dialog.
    """

    def confirm() -> None:
        try:
            on_confirm()
        except ServiceError as error:
            ui.notify(describe(error), type="negative")
        dialog.close()

    with ui.dialog() as dialog, ui.card().classes("mes-dialog"):
        ui.label(title).classes("mes-dialog-title")
        ui.label(message).classes("mes-dialog-text")
        with ui.row().classes("w-full justify-end gap-2 pt-2"):
            ui.button("Cancelar", on_click=dialog.close).props("flat no-caps").mark("dialog-cancel")
            color = "negative" if danger else "primary"
            ui.button(confirm_label, on_click=confirm).props(
                f"unelevated no-caps color={color}"
            ).mark("dialog-confirm")
    dialog.open()
    return dialog


def info_dialog(title: str, message: str) -> ui.dialog:
    """Show a message that only needs acknowledging.

    Args:
        title: Dialog title.
        message: Text to show.

    Returns:
        The open dialog.
    """
    with ui.dialog() as dialog, ui.card().classes("mes-dialog"):
        ui.label(title).classes("mes-dialog-title")
        ui.label(message).classes("mes-dialog-text")
        with ui.row().classes("w-full justify-end pt-2"):
            ui.button("Entendido", on_click=dialog.close).props("unelevated no-caps").mark(
                "dialog-ok"
            )
    dialog.open()
    return dialog
