import re

import pytest

from mes_server.web import theme
from mes_server.web.pages import initials

CSS = (theme.STATIC_DIR / "css" / "theme.css").read_text(encoding="utf-8")


def test_institutional_colors_are_defined_in_the_stylesheet():
    assert f"--mes-primary: {theme.PRIMARY.lower()};" in CSS
    assert f"--mes-accent: {theme.ACCENT.lower()};" in CSS


def test_palette_values_are_uppercase_hex():
    assert re.match(r"^#[0-9A-F]{6}$", theme.PRIMARY)
    assert re.match(r"^#[0-9A-F]{6}$", theme.ACCENT)


def test_bundled_font_and_its_license_are_present():
    assert (theme.STATIC_DIR / "fonts" / "inter-latin-wght-normal.woff2").is_file()
    assert (theme.STATIC_DIR / "fonts" / "Inter-OFL.txt").is_file()


def test_stylesheet_references_the_bundled_font():
    assert "/static/fonts/inter-latin-wght-normal.woff2" in CSS


def test_logo_is_missing_until_provided(tmp_path):
    assert theme.logo_url(theme.UNAM_LOGO, tmp_path) is None


@pytest.mark.parametrize("extension", [".svg", ".png", ".webp"])
def test_logo_is_found_with_supported_extensions(tmp_path, extension):
    (tmp_path / f"{theme.UNAM_LOGO}{extension}").write_bytes(b"logo")
    assert theme.logo_url(theme.UNAM_LOGO, tmp_path) == f"/static/branding/escudo-unam{extension}"


def test_svg_is_preferred_over_png(tmp_path):
    (tmp_path / "escudo-unam.png").write_bytes(b"png")
    (tmp_path / "escudo-unam.svg").write_bytes(b"svg")
    assert theme.logo_url(theme.UNAM_LOGO, tmp_path).endswith(".svg")


def test_unsupported_extension_is_ignored(tmp_path):
    (tmp_path / "escudo-unam.gif").write_bytes(b"gif")
    assert theme.logo_url(theme.UNAM_LOGO, tmp_path) is None


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Ingeniera Demo", "ID"), ("ada", "A"), ("Ana María López", "AM"), ("   ", "?")],
)
def test_initials(name, expected):
    assert initials(name) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(None, "—"), ("", "—"), (0, "0"), (2.5, "2.5"), ("ST-10", "ST-10")]
)
def test_cell_text(value, expected):
    from mes_server.web.components import cell_text

    assert cell_text(value) == expected
