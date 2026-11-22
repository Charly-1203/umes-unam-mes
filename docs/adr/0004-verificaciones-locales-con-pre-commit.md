# 0004. Verificaciones locales con pre-commit

- **Estado:** Aceptado
- **Fecha:** 2026-11-16

## Contexto

Se necesita garantizar estilo, formato y pruebas en cada cambio sin agregar infraestructura que
el equipo deba mantener.

## Opciones consideradas

| Opción | Ventajas | Desventajas |
|---|---|---|
| Solo pre-commit local | Sin infraestructura; retroalimentación inmediata | Depende de que cada integrante instale los hooks |
| pre-commit y GitHub Actions | Validación garantizada en cada pull request | Requiere configurar y mantener CI |
| Solo GitHub Actions | Validación centralizada | Los errores se descubren tarde |

## Decisión

Solo pre-commit local:

- Al hacer commit: verificaciones de archivos, `ruff check` y `ruff format`.
- Al hacer push: `pytest`.

## Consecuencias

- Cada integrante instala los hooks una vez con `uv run pre-commit install --install-hooks`.
- Antes de abrir un pull request se ejecuta `uv run pre-commit run --all-files`.
- Si más adelante se agrega CI, puede reutilizar la misma configuración de pre-commit.
