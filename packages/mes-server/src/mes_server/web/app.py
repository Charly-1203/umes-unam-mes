"""Web application assembly and start-up."""

from collections.abc import Callable

from nicegui import ui
from sqlalchemy import Engine

from mes_core.permissions import has_permission
from mes_server.db.models import User
from mes_server.web import catalog_pages, pages, theme
from mes_server.web import session as web_session
from mes_server.web.navigation import MODULES, Module, find_module


def build_root(engine: Engine) -> Callable[[], None]:
    """Create the root page function that NiceGUI calls for every browser visit.

    The root decides what the visitor sees: the sign-in screen when nobody is signed in,
    otherwise the application frame with the screen that matches the URL.

    Args:
        engine: Database engine used by every screen.

    Returns:
        The root page function.
    """

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
            elif module.path in SCREENS:
                SCREENS[module.path](engine, user)
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


SCREENS: dict[str, Callable[[Engine, User], None]] = {
    "/products": catalog_pages.products_page,
    "/stations": catalog_pages.stations_page,
    "/downtime-reasons": catalog_pages.downtime_reasons_page,
}
"""Sections that already have a screen; the rest show the under-construction message."""


def run(
    engine: Engine,
    *,
    host: str,
    port: int,
    storage_secret: str,
) -> None:  # pragma: no cover - starts a blocking server
    """Start the web server and block until it stops.

    Args:
        engine: Database engine.
        host: Address to listen on.
        port: Port to listen on.
        storage_secret: Secret that signs session cookies.
    """
    theme.register_static_files()
    ui.run(
        build_root(engine),
        host=host,
        port=port,
        title=pages.APP_TITLE,
        language="es",
        storage_secret=storage_secret,
        reload=False,
        show=False,
    )
