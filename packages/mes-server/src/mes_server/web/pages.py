"""Screens of the web application.

Each function builds the content of one screen. They only arrange widgets and call services;
business rules stay in :mod:`mes_server.services`. Visual styles live in
``static/css/theme.css`` and are referenced here through ``mes-*`` class names.
"""

from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui
from sqlalchemy import Engine
from sqlmodel import Session

from mes_core.permissions import has_permission
from mes_server.db.engine import session_scope
from mes_server.db.models import User
from mes_server.services import users as user_service
from mes_server.web import session as web_session
from mes_server.web import theme
from mes_server.web.navigation import ROLE_LABELS, Module, modules_for

APP_TITLE = "UNAM-MES"
APP_SUBTITLE = "Sistema de Ejecución de Manufactura"
UNIT_NAME = "Laboratorio de Automatización"
UNIVERSITY_NAME = "Universidad Nacional Autónoma de México"

HOME_PATH = "/"
HOME_TITLE = "Inicio"
HOME_ICON = "home"

ISA95_LEVELS = (
    ("Nivel 4", "ERP"),
    ("Nivel 3", "MES"),
    ("Nivel 2", "Estación de trabajo"),
    ("Nivel 1", "PLC"),
)
"""Levels shown on the sign-in screen; the MES level is highlighted."""


# ---------------------------------------------------------------------------------------------
# Shared pieces
# ---------------------------------------------------------------------------------------------
def brand_mark() -> None:
    """Show the UNAM coat of arms, or a generic mark until the installation provides it."""
    with ui.element("div").classes("mes-brand-mark"):
        url = theme.logo_url(theme.UNAM_LOGO)
        if url:
            ui.image(url).props('alt="Escudo de la UNAM"')
        else:
            ui.icon("factory", size="22px")


def initials(full_name: str) -> str:
    """Return up to two initials for an avatar.

    Args:
        full_name: Name of the user.

    Returns:
        The initials in uppercase, or ``"?"`` for a blank name.
    """
    letters = [word[0] for word in full_name.split() if word]
    return "".join(letters[:2]).upper() or "?"


# ---------------------------------------------------------------------------------------------
# Sign-in
# ---------------------------------------------------------------------------------------------
def login_page(engine: Engine) -> None:
    """Build the sign-in screen.

    Args:
        engine: Database engine.
    """
    with Session(engine) as session:
        has_admin = user_service.count_active_admins(session) > 0

    def submit() -> None:
        with session_scope(engine) as session:
            user = user_service.authenticate(session, username.value, password.value)
            user_id = user.id if user else None
        if user_id is None:
            password.value = ""
            ui.notify("Usuario o contraseña incorrectos.", type="negative")
            return
        web_session.sign_in(user_id)
        ui.navigate.reload()

    with ui.element("div").classes("mes-login"):
        with ui.element("section").classes("mes-login-hero"):
            with ui.element("div").classes("mes-brand"):
                brand_mark()
                with ui.column().classes("gap-0"):
                    ui.label(APP_TITLE).classes("mes-brand-name text-xl")
                    ui.label(UNIT_NAME).classes("mes-brand-unit text-sm")
            with ui.column().classes("gap-5 max-w-md"):
                ui.element("div").classes("mes-accent-bar")
                ui.html(f"<h1>{APP_SUBTITLE}</h1>")
                ui.html(
                    "<p>De la orden del ERP a la ejecución en cada estación: recetas, "
                    "trazabilidad y estado de la línea en un solo lugar.</p>"
                )
            with ui.column().classes("gap-2 w-full max-w-md"):
                for level, name in ISA95_LEVELS:
                    css = "mes-level mes-level--active" if name == "MES" else "mes-level"
                    with ui.element("div").classes(css):
                        ui.label(level).classes("mes-level-number")
                        ui.label(name).classes("text-sm font-semibold")

        with (
            ui.element("section").classes("mes-login-panel"),
            ui.element("div").classes("mes-login-form"),
        ):
            with ui.column().classes("gap-1"):
                ui.label("Iniciar sesión").classes("text-2xl font-bold")
                ui.label("Usa la cuenta que te asignó el administrador.").classes(
                    "mes-page-subtitle"
                )
            username = ui.input("Usuario").props("outlined autofocus").classes("w-full")
            password = (
                ui.input("Contraseña", password=True, password_toggle_button=True)
                .props("outlined")
                .classes("w-full")
            )
            username.on("keydown.enter", lambda: password.run_method("focus"))
            password.on("keydown.enter", submit)
            ui.button("Entrar", on_click=submit).props("unelevated no-caps size=lg").classes(
                "w-full"
            )
            if not has_admin:
                with ui.element("div").classes("mes-notice"):
                    ui.label("Aún no hay administradores.").classes("font-semibold")
                    ui.label("Crea el primero desde la terminal:")
                    ui.code("uv run mes-server users create-admin", language="powershell")
            with ui.row().classes("items-center gap-3 pt-2"):
                unit_logo = theme.logo_url(theme.UNIT_LOGO)
                if unit_logo:
                    ui.image(unit_logo).props('alt="Escudo de la dependencia"').classes("w-10")
                ui.label(UNIVERSITY_NAME).classes("mes-page-subtitle text-xs")


# ---------------------------------------------------------------------------------------------
# Application frame
# ---------------------------------------------------------------------------------------------
@dataclass
class Shell:
    """Frame shared by every screen once signed in.

    Attributes:
        drawer: Side navigation menu.
        menu: Refreshable menu; call ``menu.refresh(path)`` to highlight a section.
    """

    drawer: ui.left_drawer
    menu: Callable[..., None]

    def show(self, path: str, title: str, build: Callable[[], None]) -> None:
        """Render a screen inside the frame.

        Args:
            path: URL path of the screen, used to highlight the menu.
            title: Name shown in the top bar.
            build: Function that builds the screen's content.
        """
        self.menu.refresh(path)
        with ui.element("div").classes("mes-topbar"):
            ui.button(icon="menu", on_click=self.drawer.toggle).props(
                'flat round dense color=primary aria-label="Abrir menú"'
            ).classes("lt-md")
            ui.label(APP_TITLE)
            ui.label("/").props('aria-hidden="true"')
            ui.label(title).classes("mes-topbar-current")
        with ui.element("div").classes("mes-page"):
            build()


def layout(user: User) -> Shell:
    """Build the frame: side menu with brand, sections and the signed-in user.

    Args:
        user: Signed-in user.

    Returns:
        The frame, used to render each screen.
    """

    def sign_out() -> None:
        web_session.sign_out()
        # A full reload makes the root page run again and show the sign-in screen.
        ui.navigate.reload()

    with ui.left_drawer().props("width=264 breakpoint=1024").classes("mes-drawer") as drawer:
        with ui.element("div").classes("mes-brand"):
            brand_mark()
            with ui.column().classes("gap-0"):
                ui.label(APP_TITLE).classes("mes-brand-name")
                ui.label(UNIT_NAME).classes("mes-brand-unit")

        @ui.refreshable
        def menu(active: str = HOME_PATH) -> None:
            with ui.column().classes("gap-0.5 w-full"):
                _menu_item(HOME_TITLE, HOME_PATH, HOME_ICON, active)
                for module in modules_for(user.role):
                    _menu_item(module.title, module.path, module.icon, active)

        menu()
        ui.space()
        with ui.element("div").classes("mes-user-card"):
            ui.label(initials(user.full_name)).classes("mes-avatar")
            with ui.column().classes("gap-0 min-w-0 grow"):
                ui.label(user.full_name).classes("text-sm font-semibold ellipsis")
                ui.label(ROLE_LABELS[user.role]).classes("mes-brand-unit")
            ui.button(icon="logout", on_click=sign_out).props(
                'flat round color=white aria-label="Cerrar sesión"'
            ).mark("sign-out").tooltip("Cerrar sesión")
    return Shell(drawer=drawer, menu=menu)


def _menu_item(title: str, path: str, icon: str, active: str) -> None:
    css = "mes-nav-item mes-nav-item--active" if path == active else "mes-nav-item"
    with ui.element("div").classes(css).on("click", lambda: ui.navigate.to(path)):
        ui.icon(icon, size="20px")
        ui.label(title)


# ---------------------------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------------------------
def home_page(user: User) -> None:
    """Build the home screen: a greeting and the sections the user may open.

    Args:
        user: Signed-in user.
    """
    modules = modules_for(user.role)
    with ui.column().classes("gap-1"):
        ui.label(f"Hola, {user.full_name}").classes("mes-page-title")
        if modules:
            ui.label("Estas son las secciones disponibles para tu rol.").classes(
                "mes-page-subtitle"
            )

    if not modules:
        with ui.element("div").classes("mes-panel"):
            ui.label("Tu trabajo se realiza en la pantalla de tu estación.")
        return

    with ui.element("div").classes("mes-card-grid"):
        for module in modules:
            _module_card(module)

    with ui.element("div").classes("mes-panel"):
        ui.label("Estado de la línea").classes("mes-panel-title")
        ui.label("Aún no hay estaciones conectadas.").classes("mes-empty")


def _module_card(module: Module) -> None:
    with (
        ui.element("div")
        .classes("mes-module-card")
        .on("click", lambda: ui.navigate.to(module.path))
    ):
        with ui.element("div").classes("mes-module-icon"):
            ui.icon(module.icon, size="22px")
        with ui.column().classes("gap-1 min-w-0"):
            ui.label(module.title).classes("mes-module-title")
            ui.label(module.description).classes("mes-module-description")
            if not module.available:
                ui.label("En construcción").classes("mes-badge-wip")


def module_page(module: Module, user: User) -> None:
    """Build a section screen, or an access-denied message when the role lacks permission.

    Args:
        module: Section to show.
        user: Signed-in user.
    """
    if not has_permission(user.role, module.permission):
        access_denied()
        return
    with ui.column().classes("gap-1"):
        ui.label(module.title).classes("mes-page-title")
        ui.label(module.description).classes("mes-page-subtitle")
    if not module.available:
        with ui.element("div").classes("mes-panel"):
            ui.label("Esta sección está en construcción.").classes("mes-empty")


def access_denied() -> None:
    """Build the message shown when a user opens a section their role does not allow."""
    with ui.element("div").classes("mes-panel items-center text-center"):
        ui.icon("lock", size="48px", color="negative")
        ui.label("No tienes permiso para abrir esta sección.").classes("mes-panel-title")
        ui.button("Ir al inicio", on_click=lambda: ui.navigate.to(HOME_PATH)).props(
            "unelevated no-caps"
        )
