"""Signed-in user of the current browser.

NiceGUI keeps a per-browser storage on the server, identified by a signed cookie. Only the
user's id is stored there; the user is loaded from the database on every page so a deactivated
user or a changed role takes effect immediately.
"""

from nicegui import app
from sqlalchemy import Engine
from sqlmodel import Session

from mes_server.db.models import User

_USER_ID_KEY = "user_id"


def sign_in(user_id: int) -> None:
    """Remember the user in the browser session.

    Args:
        user_id: Id of the authenticated user.
    """
    app.storage.user[_USER_ID_KEY] = user_id


def sign_out() -> None:
    """Forget the signed-in user."""
    app.storage.user.pop(_USER_ID_KEY, None)


def current_user(engine: Engine) -> User | None:
    """Load the signed-in user, if the session still refers to an active one.

    Args:
        engine: Database engine.

    Returns:
        The user, or ``None`` when nobody is signed in or the user is no longer active.
    """
    user_id = app.storage.user.get(_USER_ID_KEY)
    if user_id is None:
        return None
    with Session(engine, expire_on_commit=False) as session:
        user = session.get(User, user_id)
    if user is None or not user.is_active:
        sign_out()
        return None
    return user
