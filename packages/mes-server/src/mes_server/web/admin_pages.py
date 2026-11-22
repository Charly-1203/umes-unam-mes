"""Administration screens: user management, backups, course reset and audit log."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from nicegui import ui
from sqlalchemy import Engine
from sqlmodel import Session

from mes_core.enums import Role
from mes_server.db.engine import session_scope
from mes_server.db.models import User
from mes_server.services import audit, backups, course_reset
from mes_server.services import users as user_service
from mes_server.services.course_reset import CONFIRMATION_WORD, ResetLevel
from mes_server.services.errors import ServiceError, ValidationError
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
from mes_server.web.messages import TABLE_LABELS, describe, describe_usage
from mes_server.web.navigation import ROLE_LABELS

Row = dict[str, Any]

ROLE_OPTIONS = {role.value: ROLE_LABELS[role] for role in Role}


def format_datetime(value: datetime) -> str:
    """Show a timestamp in the server's local time.

    Args:
        value: Timezone-aware timestamp.

    Returns:
        The timestamp as ``dd/mm/aaaa hh:mm``.
    """
    return value.astimezone().strftime("%d/%m/%Y %H:%M")


def format_size(size_bytes: int) -> str:
    """Show a file size in KB or MB.

    Args:
        size_bytes: Size in bytes.

    Returns:
        The size, such as ``"84 KB"`` or ``"1.2 MB"``.
    """
    if size_bytes < 1024 * 1024:
        return f"{max(1, round(size_bytes / 1024))} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------------------------
USER_CREATE_FIELDS = (
    Field("username", "Usuario", hint="De 3 a 64 caracteres: minúsculas, números, . _ -"),
    Field("full_name", "Nombre completo"),
    Field("role", "Rol", kind="select", options=ROLE_OPTIONS),
    Field("password", "Contraseña", kind="password"),
    Field("password_confirm", "Repite la contraseña", kind="password"),
)

USER_EDIT_FIELDS = (
    Field("username", "Usuario", read_only=True),
    Field("full_name", "Nombre completo"),
    Field("role", "Rol", kind="select", options=ROLE_OPTIONS),
)

PASSWORD_FIELDS = (
    Field("password", "Contraseña nueva", kind="password"),
    Field("password_confirm", "Repite la contraseña", kind="password"),
)


def _check_passwords_match(values: dict[str, Any]) -> None:
    if values["password"] != values["password_confirm"]:
        raise ValidationError(
            "Passwords do not match.", code="password_mismatch", field="password_confirm"
        )


def users_page(engine: Engine, user: User) -> None:
    """Build the user management screen.

    Args:
        engine: Database engine.
        user: Signed-in administrator.
    """
    state = {"show_inactive": False}

    def apply(action: Callable[[Session], Any], message: str) -> None:
        with session_scope(engine) as session:
            action(session)
        table.refresh()
        ui.notify(message, type="positive")

    def create(values: dict[str, Any]) -> None:
        _check_passwords_match(values)
        apply(
            lambda s: user_service.create_user(
                s,
                username=values["username"],
                full_name=values["full_name"],
                password=values["password"],
                role=Role(values["role"]),
            ),
            "Usuario creado.",
        )

    def open_create() -> None:
        form_dialog(
            "Nuevo usuario",
            USER_CREATE_FIELDS,
            create,
            initial={"role": Role.OPERATOR.value},
        )

    def open_edit(row: Row) -> None:
        form_dialog(
            f"Editar {row['username']}",
            USER_EDIT_FIELDS,
            lambda v: apply(
                lambda s: user_service.update_user(
                    s, row["id"], full_name=v["full_name"], role=Role(v["role"]), actor_id=user.id
                ),
                "Cambios guardados.",
            ),
            initial=row,
        )

    def open_password(row: Row) -> None:
        def save(values: dict[str, Any]) -> None:
            _check_passwords_match(values)
            apply(
                lambda s: user_service.set_password(s, row["id"], values["password"]),
                "Contraseña actualizada.",
            )

        form_dialog(f"Nueva contraseña para {row['username']}", PASSWORD_FIELDS, save)

    def toggle_active(row: Row) -> None:
        if row["is_active"]:
            confirm_dialog(
                f"Desactivar {row['username']}",
                "No podrá iniciar sesión. Su historia se conserva y puedes reactivarlo después.",
                lambda: apply(
                    lambda s: user_service.set_user_active(s, row["id"], False, actor_id=user.id),
                    "Usuario desactivado.",
                ),
                confirm_label="Desactivar",
            )
        else:
            apply(
                lambda s: user_service.set_user_active(s, row["id"], True, actor_id=user.id),
                "Usuario activado.",
            )

    def start_delete(row: Row) -> None:
        with Session(engine) as session:
            usage = user_service.user_usage(session, row["id"])
        if usage:
            info_dialog(
                f"No se puede borrar {row['username']}",
                f"Tiene {describe_usage(usage)}. Puedes desactivarlo; su historia se limpia con "
                "el reinicio de curso.",
            )
            return
        confirm_dialog(
            f"Borrar {row['username']}",
            "Se borrará el usuario de forma permanente. Esta acción no se puede deshacer.",
            lambda: apply(
                lambda s: user_service.delete_user(
                    s, row["id"], actor_role=user.role, actor_id=user.id
                ),
                "Usuario borrado.",
            ),
            confirm_label="Borrar",
            danger=True,
        )

    def row_actions(row: Row) -> None:
        name = row["username"]
        icon_button("edit", "Editar", lambda: open_edit(row), marker=f"edit-{name}")
        icon_button(
            "key", "Cambiar contraseña", lambda: open_password(row), marker=f"password-{name}"
        )
        if row["is_self"]:
            return
        if row["is_active"]:
            icon_button(
                "block", "Desactivar", lambda: toggle_active(row), marker=f"deactivate-{name}"
            )
        else:
            icon_button(
                "check_circle", "Activar", lambda: toggle_active(row), marker=f"activate-{name}"
            )
        icon_button(
            "delete", "Borrar", lambda: start_delete(row), marker=f"delete-{name}", danger=True
        )

    def username_cell(row: Row) -> None:
        with ui.row().classes("items-center gap-2 no-wrap"):
            ui.label(row["username"]).classes("mes-cell-code")
            if row["is_self"]:
                ui.label("tú").classes("mes-chip mes-chip--inactive")

    with page_header("Usuarios", "Cuentas de acceso y su rol."):
        ui.button("Nuevo usuario", icon="person_add", on_click=open_create).props(
            "unelevated no-caps"
        ).mark("user-new")

    with ui.element("div").classes("mes-panel"):
        with ui.element("div").classes("mes-toolbar"):
            ui.switch(
                "Mostrar inactivos",
                on_change=lambda e: (state.update(show_inactive=e.value), table.refresh()),
            ).mark("show-inactive")

        @ui.refreshable
        def table() -> None:
            with Session(engine) as session:
                rows = [
                    {
                        "id": u.id,
                        "username": u.username,
                        "full_name": u.full_name,
                        "role": u.role.value,
                        "role_label": ROLE_LABELS[u.role],
                        "is_active": u.is_active,
                        "is_self": u.id == user.id,
                    }
                    for u in user_service.list_users(session)
                    if u.is_active or state["show_inactive"]
                ]
            data_table(
                (
                    Column("Usuario", "username", render=username_cell),
                    Column("Nombre", "full_name"),
                    Column("Rol", "role_label"),
                    Column("Estado", "is_active", render=lambda r: status_chip(r["is_active"])),
                ),
                rows,
                actions=row_actions,
                empty_text="No hay usuarios.",
            )

        table()


# ---------------------------------------------------------------------------------------------
# Administration: backups, course reset and audit log
# ---------------------------------------------------------------------------------------------
LEVEL_OPTIONS: dict[str, str] = {
    ResetLevel.PRODUCTION.value: "Producción: órdenes, piezas, registros de ejecución y paros",
    ResetLevel.CATALOGS.value: (
        "Producción y catálogos: además productos, recetas y motivos de paro"
    ),
    ResetLevel.EVERYTHING.value: "Todo: además los usuarios que no son administradores",
}

LEVEL_LABELS: dict[str, str] = {
    ResetLevel.PRODUCTION.value: "producción",
    ResetLevel.CATALOGS.value: "producción y catálogos",
    ResetLevel.EVERYTHING.value: "todo",
}

ACTION_LABELS: dict[str, str] = {
    "course_reset": "Reinicio de curso",
    "backup_created": "Respaldo manual",
}


def describe_reason(reason: str) -> str:
    """Translate a backup reason for display.

    Args:
        reason: Reason stored in the manifest.

    Returns:
        The reason in Spanish.
    """
    if reason == "manual":
        return "Manual"
    for level, label in LEVEL_LABELS.items():
        if reason == f"course-reset-{level}":
            return f"Antes de reiniciar ({label})"
    return reason


def describe_counts(counts: dict[str, int]) -> str:
    """Describe row counts per table in Spanish.

    Args:
        counts: Rows per table name.

    Returns:
        A phrase such as ``"3 órdenes de trabajo, 12 piezas"``, or ``"nada"``.
    """
    parts = [f"{n} {TABLE_LABELS.get(table, table)}" for table, n in counts.items() if n]
    return ", ".join(parts) if parts else "nada"


def describe_audit(action: str, detail: dict[str, Any]) -> str:
    """Summarize an audit entry's detail for display.

    Args:
        action: Action identifier.
        detail: Entry detail.

    Returns:
        A short Spanish description.
    """
    if action == "course_reset":
        level = LEVEL_LABELS.get(detail.get("level", ""), detail.get("level", ""))
        return f"Nivel: {level}. Borrado: {describe_counts(detail.get('deleted', {}))}."
    if action == "backup_created":
        return f"Archivo: {detail.get('backup', '')}"
    return ""


def admin_page(engine: Engine, user: User, database_url: str, backup_dir: Path | None) -> None:
    """Build the administration screen.

    Args:
        engine: Database engine.
        user: Signed-in administrator.
        database_url: SQLAlchemy URL of the database, used for backups.
        backup_dir: Folder for backups, or ``None`` when backups are not available.
    """
    page_header("Administración", "Respaldos, reinicio de curso y bitácora.")
    # Panels built first notify the ones built later through these callbacks.
    on_backup: list[Callable[[], None]] = []
    on_change: list[Callable[[], None]] = []
    _backups_panel(engine, user, database_url, backup_dir, on_backup, on_change)
    _reset_panel(engine, user, database_url, backup_dir, on_backup, on_change)
    on_change.append(_audit_panel(engine))


def _notify(callbacks: list[Callable[[], None]]) -> None:
    for callback in callbacks:
        callback()


def _backups_panel(
    engine: Engine,
    user: User,
    database_url: str,
    backup_dir: Path | None,
    on_backup: list[Callable[[], None]],
    on_change: list[Callable[[], None]],
) -> None:
    with ui.element("div").classes("mes-panel"):
        if backup_dir is None:
            ui.label("Respaldos").classes("mes-panel-title")
            ui.label(
                "Los respaldos solo están disponibles cuando la base de datos es un archivo SQLite."
            ).classes("mes-empty")
            return

        def create() -> None:
            try:
                info = course_reset.backup_now(
                    engine, database_url, backup_dir, actor=user.username, actor_role=user.role
                )
            except ServiceError as error:
                ui.notify(describe(error), type="negative")
                return
            listing.refresh()
            _notify(on_change)
            ui.notify(f"Respaldo creado: {info.file_name}", type="positive")

        with ui.element("div").classes("mes-toolbar"):
            ui.label("Respaldos").classes("mes-panel-title")
            ui.button("Crear respaldo", icon="backup", on_click=create).props(
                "unelevated no-caps"
            ).mark("backup-create")
        ui.label(
            f"Se guardan en «{backup_dir.resolve()}». Restaurar desde la aplicación estará "
            "disponible más adelante; mientras tanto consulta el procedimiento manual en la "
            "documentación."
        ).classes("mes-page-subtitle")

        @ui.refreshable
        def listing() -> None:
            rows = [
                {
                    "file_name": b.file_name,
                    "path": b.path,
                    "created": format_datetime(b.created_at),
                    "created_by": b.created_by,
                    "reason": describe_reason(b.reason),
                    "size": format_size(b.size_bytes),
                    "revision": b.schema_revision,
                }
                for b in backups.list_backups(backup_dir)
            ]
            data_table(
                (
                    Column("Fecha", "created"),
                    Column("Creado por", "created_by"),
                    Column("Motivo", "reason"),
                    Column("Tamaño", "size", css="mes-cell-number"),
                    Column("Esquema", "revision"),
                ),
                rows,
                actions=lambda r: icon_button(
                    "download",
                    "Descargar",
                    lambda: ui.download.file(r["path"], r["file_name"]),
                    marker=f"download-{r['file_name']}",
                ),
                empty_text="Aún no hay respaldos.",
            )

        listing()
        on_backup.append(listing.refresh)


def _reset_panel(
    engine: Engine,
    user: User,
    database_url: str,
    backup_dir: Path | None,
    on_backup: list[Callable[[], None]],
    on_change: list[Callable[[], None]],
) -> None:
    with ui.element("div").classes("mes-panel mes-panel--danger"):
        ui.label("Reinicio de curso").classes("mes-panel-title")
        ui.label(
            "Deja el sistema listo para la siguiente generación. Antes de borrar se crea un "
            "respaldo automático. Las estaciones, los administradores y la bitácora se conservan."
        ).classes("mes-page-subtitle")
        if backup_dir is None:
            ui.label("No disponible: requiere respaldos.").classes("mes-empty")
            return

        level = ui.radio(LEVEL_OPTIONS, value=ResetLevel.PRODUCTION.value).mark("reset-level")

        @ui.refreshable
        def preview() -> None:
            with Session(engine) as session:
                counts = course_reset.preview(session, ResetLevel(level.value))
            ui.label(f"Se borrará: {describe_counts(counts)}.").classes("mes-dialog-text").mark(
                "reset-preview"
            )

        preview()
        level.on_value_change(preview.refresh)

        confirmation = (
            ui.input(f"Escribe {CONFIRMATION_WORD} para confirmar")
            .props("outlined")
            .classes("w-full max-w-sm")
            .mark("reset-confirmation")
        )

        def run_reset() -> None:
            try:
                result = course_reset.reset_course(
                    engine,
                    database_url,
                    backup_dir,
                    ResetLevel(level.value),
                    actor=user.username,
                    actor_role=user.role,
                    confirmation=confirmation.value or "",
                )
            except ServiceError as error:
                ui.notify(describe(error), type="negative")
                return
            confirmation.value = ""
            preview.refresh()
            _notify(on_backup)
            _notify(on_change)
            info_dialog(
                "Curso reiniciado",
                f"Se borró: {describe_counts(result.deleted)}. "
                f"Respaldo previo: {result.backup.file_name}.",
            )

        button = (
            ui.button("Reiniciar curso", icon="restart_alt", on_click=run_reset)
            .props("unelevated no-caps color=negative")
            .classes("self-start")
            .mark("reset-run")
        )
        button.bind_enabled_from(
            confirmation, "value", backward=lambda text: (text or "").strip() == CONFIRMATION_WORD
        )


def _audit_panel(engine: Engine) -> Callable[[], None]:
    @ui.refreshable
    def log() -> None:
        with Session(engine) as session:
            rows = [
                {
                    "created": format_datetime(entry.created_at),
                    "actor": entry.actor,
                    "action": ACTION_LABELS.get(entry.action, entry.action),
                    "detail": describe_audit(entry.action, entry.detail),
                }
                for entry in audit.list_recent(session)
            ]
        data_table(
            (
                Column("Fecha", "created"),
                Column("Usuario", "actor"),
                Column("Acción", "action"),
                Column("Detalle", "detail"),
            ),
            rows,
            empty_text="Aún no hay acciones registradas.",
        )

    with ui.element("div").classes("mes-panel"):
        ui.label("Bitácora").classes("mes-panel-title")
        log()
    return log.refresh
