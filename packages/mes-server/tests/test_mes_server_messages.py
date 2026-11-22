import pytest

from mes_server.services.errors import (
    AlreadyExistsError,
    InUseError,
    NotFoundError,
    PermissionDeniedError,
    ServiceError,
    ValidationError,
)
from mes_server.web.messages import GENERIC_ERROR, describe, describe_usage


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ValidationError("x", code="blank", field="name"), "El nombre es obligatorio."),
        (ValidationError("x", code="too_long", field="code"), "El código es demasiado largo."),
        (ValidationError("x", code="not_positive", field="quantity"),
         "La cantidad debe ser mayor que cero."),
        (ValidationError("x", code="not_a_number", field="quantity"),
         "La cantidad debe ser un número."),
        (AlreadyExistsError("x", field="code"), "Ya existe un registro con ese código."),
        (AlreadyExistsError("x", field="component_code"),
         "Ese componente ya está en la lista de materiales."),
        (AlreadyExistsError("x", field="username"), "Ya existe un usuario con ese nombre."),
        (NotFoundError("x"), "El registro ya no existe. Recarga la página."),
        (PermissionDeniedError("x"), "Tu rol no permite esta acción."),
        (ValidationError("x", code="password_too_short"), "La contraseña es demasiado corta."),
        (ServiceError("x"), GENERIC_ERROR),
    ],
)  # fmt: skip
def test_errors_are_described_in_spanish(error, expected):
    assert describe(error) == expected


def test_in_use_suggests_deactivating():
    assert "Desactívalo" in describe(InUseError("x"))


def test_code_format_mentions_allowed_characters():
    assert "sin espacios" in describe(ValidationError("x", code="code_format", field="code"))


def test_username_format_is_explained():
    assert "3 a 64" in describe(ValidationError("x", code="username_format", field="username"))


def test_unknown_field_uses_a_generic_subject():
    assert describe(ValidationError("x", code="blank", field="other")) == "El valor es obligatorio."


def test_error_keeps_its_class_code_unless_overridden():
    assert NotFoundError("x").code == "not_found"
    assert ValidationError("x", code="blank").code == "blank"


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        ({}, ""),
        ({"recipes": 1}, "1 receta"),
        ({"recipes": 2}, "2 recetas"),
        ({"recipes": 1, "work orders": 3}, "1 receta y 3 órdenes de trabajo"),
        ({"recipe steps": 2, "execution records": 1, "downtime events": 4},
         "2 pasos de receta, 1 registro de ejecución y 4 paros"),
        ({"unknown": 2}, "2 unknown"),
    ],
)  # fmt: skip
def test_describe_usage(usage, expected):
    assert describe_usage(usage) == expected
