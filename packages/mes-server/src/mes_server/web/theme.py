"""Visual identity of the web application.

Colors, fonts and layout rules live in ``static/css/theme.css``; this module registers the
static files, applies the palette to the component library and resolves the institutional
logos, which each installation provides in ``static/branding/``.
"""

from pathlib import Path

from nicegui import app, ui

STATIC_DIR = Path(__file__).parent / "static"
STATIC_URL = "/static"
BRANDING_DIR = STATIC_DIR / "branding"

PRIMARY = "#013B75"
"""Azul UNAM (Pantone 540)."""

ACCENT = "#D9A500"
"""Oro UNAM (Pantone 117)."""

LOGO_EXTENSIONS = (".svg", ".png", ".webp")

UNAM_LOGO = "escudo-unam"
"""File name, without extension, of the UNAM coat of arms in ``static/branding/``."""

UNIT_LOGO = "escudo-dependencia"
"""File name, without extension, of the faculty or school logo in ``static/branding/``."""


def register_static_files() -> None:
    """Serve the theme's CSS, fonts and logos under ``/static``.

    Call once, before the server starts.
    """
    app.add_static_files(STATIC_URL, STATIC_DIR)


def apply() -> None:
    """Apply the theme to the page being built."""
    ui.colors(primary=PRIMARY, secondary=ACCENT, accent=ACCENT)
    ui.add_head_html(f'<link rel="stylesheet" href="{STATIC_URL}/css/theme.css">')


def logo_url(name: str, branding_dir: Path = BRANDING_DIR) -> str | None:
    """Return the URL of a logo if the installation provides it.

    Args:
        name: File name without extension, such as :data:`UNAM_LOGO`.
        branding_dir: Folder that holds the logos.

    Returns:
        The URL to the first file found with a supported extension, or ``None``.
    """
    for extension in LOGO_EXTENSIONS:
        if (branding_dir / f"{name}{extension}").is_file():
            return f"{STATIC_URL}/branding/{name}{extension}"
    return None
