"""Web application assembly and start-up."""

from collections.abc import Callable

from nicegui import ui
from sqlalchemy import Engine

from mes_server.web import pages, theme
from mes_server.web import session as web_session
from mes_server.web.navigation import MODULES


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
        routes: dict[str, Callable[[], None]] = {
            pages.HOME_PATH: lambda: shell.show(
                pages.HOME_PATH, pages.HOME_TITLE, lambda: pages.home_page(user)
            )
        }
        for module in MODULES:
            routes[module.path] = lambda m=module: shell.show(
                m.path, m.title, lambda: pages.module_page(m, user)
            )
        ui.sub_pages(routes)

    return root


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
