"""Spanish texts for the errors that services report.

Services raise errors with a stable ``code`` and, when it applies, the ``field`` involved. This
module turns them into the sentences users read, so the wording lives in one place.
"""

from mes_server.services.errors import ServiceError

FIELD_LABELS: dict[str, str] = {
    "code": "El código",
    "name": "El nombre",
    "description": "La descripción",
    "component_code": "El componente",
    "quantity": "La cantidad",
    "unit_of_measure": "La unidad",
    "username": "El usuario",
    "password": "La contraseña",
    "full_name": "El nombre completo",
}
"""How each input field is named at the start of a sentence."""

REFERENCE_LABELS: dict[str, tuple[str, str]] = {
    "recipes": ("receta", "recetas"),
    "work orders": ("orden de trabajo", "órdenes de trabajo"),
    "recipe steps": ("paso de receta", "pasos de receta"),
    "execution records": ("registro de ejecución", "registros de ejecución"),
    "downtime events": ("paro", "paros"),
}
"""Singular and plural Spanish names of the records that can reference a catalog entry."""

GENERIC_ERROR = "No se pudo completar la acción."


def _field(error: ServiceError) -> str:
    return FIELD_LABELS.get(error.field or "", "El valor")


def describe(error: ServiceError) -> str:
    """Return the Spanish sentence that explains a service error.

    Args:
        error: Error raised by a service.

    Returns:
        A sentence ready to show to the user.
    """
    field = _field(error)
    match error.code:
        case "blank":
            return f"{field} es obligatorio."
        case "too_long":
            return f"{field} es demasiado largo."
        case "code_format":
            return f"{field} solo admite letras, números, punto, guion y guion bajo, sin espacios."
        case "already_exists" if error.field == "component_code":
            return "Ese componente ya está en la lista de materiales."
        case "already_exists" if error.field == "username":
            return "Ya existe un usuario con ese nombre."
        case "already_exists":
            return "Ya existe un registro con ese código."
        case "not_positive":
            return f"{field} debe ser mayor que cero."
        case "not_a_number":
            return f"{field} debe ser un número."
        case "not_found":
            return "El registro ya no existe. Recarga la página."
        case "in_use":
            return (
                "No se puede borrar porque tiene historia. "
                "Desactívalo o espera al reinicio de curso."
            )
        case "permission_denied":
            return "Tu rol no permite esta acción."
        case "username_format":
            return (
                "El usuario debe tener de 3 a 64 caracteres: minúsculas, números, "
                "punto, guion o guion bajo."
            )
        case "password_too_short":
            return "La contraseña es demasiado corta."
        case _:
            return GENERIC_ERROR


def describe_usage(usage: dict[str, int]) -> str:
    """Describe in Spanish which records reference a catalog entry.

    Args:
        usage: Counts keyed by reference label, as returned by the ``*_usage`` services.

    Returns:
        A phrase such as ``"2 recetas y 1 orden de trabajo"``.
    """
    parts = []
    for label, count in usage.items():
        singular, plural = REFERENCE_LABELS.get(label, (label, label))
        parts.append(f"{count} {singular if count == 1 else plural}")
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " y " + parts[-1]
