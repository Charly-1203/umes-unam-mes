"""Web application assembly and start-up."""

from collections.abc import Callable
from pathlib import Path

from nicegui import ui
from sqlalchemy import Engine

from mes_core.permissions import has_permission
from mes_server.db.models import User
from mes_server.web import admin_pages, catalog_pages, pages, theme
from mes_server.web import session as web_session
from mes_server.web.navigation import MODULES, Module, find_module

Screen = Callable[[Engine, User], None]


def build_screens(database_url: str | None, backup_dir: Path | None) -> dict[str, Screen]:
    """Map each section that already has a screen to the function that builds it.

    Sections not listed show the under-construction message.

    Args:
        database_url: SQLAlchemy URL of the database, used by the administration screen.
        backup_dir: Folder for backups, or ``None`` when backups are not available.

    Returns:
        Screen builders keyed by section path.
    """
    return {
        "/products": catalog_pages.products_page,
        "/stations": catalog_pages.stations_page,
        "/downtime-reasons": catalog_pages.downtime_reasons_page,
        "/users": admin_pages.users_page,
        "/admin": lambda engine, user: admin_pages.admin_page(
            engine, user, database_url or "", backup_dir if database_url else None
        ),
    }


def build_root(
    engine: Engine, *, database_url: str | None = None, backup_dir: Path | None = None
) -> Callable[[], None]:
    """Create the root page function that NiceGUI calls for every browser visit.

    The root decides what the visitor sees: the sign-in screen when nobody is signed in,
    otherwise the application frame with the screen that matches the URL.

    Args:
        engine: Database engine used by every screen.
        database_url: SQLAlchemy URL of the same database; needed for backups.
        backup_dir: Folder for backups; ``None`` disables backups and the course reset.

    Returns:
        The root page function.
    """
    screens = build_screens(database_url, backup_dir)

    def root() -> None:
        theme.apply()
        user = web_session.current_user(engine)
        if user is None:
            pages.login_page(engine)
            return

        shell = pages.layout(user)

        def section(module: Module, build: Callable[[], None] | None = None) -> None:
            """Show a section, or the access-denied message if the role lacks permission."""
            if not has_permission(user.role, module.permission):
                pages.access_denied()
            elif build is not None:
                build()
            elif module.path in screens:
                screens[module.path](engine, user)
            else:
                pages.module_page(module, user)

        routes: dict[str, Callable[..., None]] = {
            pages.HOME_PATH: lambda: shell.show(
                pages.HOME_PATH, pages.HOME_TITLE, lambda: pages.home_page(user)
            )
        }
        for module in MODULES:
            routes[module.path] = lambda m=module: shell.show(m.path, m.title, lambda: section(m))

        products_module = find_module("/products")
        routes["/products/{product_id}"] = lambda product_id: shell.show(
            products_module.path,
            products_module.title,
            lambda: section(
                products_module,
                lambda: catalog_pages.product_detail_page(engine, user, product_id),
            ),
        )
        ui.sub_pages(routes)

    return root


def run(
    engine: Engine,
    *,
    host: str,
    port: int,
    storage_secret: str,
    database_url: str,
    backup_dir: Path | None,
) -> None:  # pragma: no cover - starts a blocking server
    """Start the web server and block until it stops.

    Args:
        engine: Database engine.
        host: Address to listen on.
        port: Port to listen on.
        storage_secret: Secret that signs session cookies.
        database_url: SQLAlchemy URL of the database, used for backups.
        backup_dir: Folder for backups, or ``None`` when backups are not available.
    """
    theme.register_static_files()
    ui.run(
        build_root(engine, database_url=database_url, backup_dir=backup_dir),
        host=host,
        port=port,
        title=pages.APP_TITLE,
        language="es",
        storage_secret=storage_secret,
        reload=False,
        show=False,
    )
