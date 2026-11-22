# Guía de contribución

## Flujo de trabajo

1. Crea una rama desde `main` con un nombre descriptivo: `feature/<tema>`, `fix/<tema>` o
   `docs/<tema>`.
2. Haz cambios pequeños y enfocados: **un pull request por módulo o funcionalidad**.
3. Antes de abrir el pull request, todas las verificaciones locales deben pasar:
   ```powershell
   uv run pre-commit run --all-files
   uv run pytest
   ```
4. Describe en el pull request qué cambia, por qué y cómo se probó.
5. Si el cambio implica una decisión de arquitectura, agrega un ADR en `docs/adr`.

## Verificaciones locales

El proyecto no usa integración continua; la calidad se garantiza con `pre-commit`:

| Momento | Verificaciones |
|---|---|
| `git commit` | Espacios y fin de archivo, YAML/TOML válidos, finales de línea LF, `ruff check` y `ruff format` |
| `git push` | Pruebas unitarias con `pytest` |

Instálalas una sola vez por clon con `uv run pre-commit install --install-hooks`.

## Convenciones

### Idioma

- **Código en inglés**: nombres, docstrings, comentarios y mensajes de error.
- **Documentación en español**: README, guías y ADR, pensados para el curso.

### Código

- Python 3.13 con anotaciones de tipo en toda función pública.
- Docstrings con el estilo de Google en módulos, clases y funciones públicas.
- Longitud máxima de línea: 100 caracteres.
- El formato lo decide `ruff format`; no se discute en revisiones.

### Dependencias entre paquetes

| Paquete | Puede depender de |
|---|---|
| `mes-core` | Ningún paquete del workspace |
| `mes-server` | `mes-core` |
| `mes-gateway` | `mes-core` |
| `mes-erp-sim` | `mes-core` |

Estas reglas se validan con pruebas en cada paquete. El gateway y el simulador de ERP se
comunican con el servidor solo por mensajes o por su API, nunca importando su código.

### Pruebas

- Cada paquete tiene su carpeta `tests/`.
- Los archivos de prueba llevan el nombre del paquete para evitar colisiones:
  `test_<modulo>_<tema>.py`.
- El nombre de cada prueba describe el comportamiento esperado.
- Toda funcionalidad nueva incluye sus pruebas en el mismo pull request.

### Cambios al modelo de datos

Todo cambio en `mes_server/db/models.py` va acompañado de una migración en el mismo pull
request. Desde la raíz del repositorio:

```powershell
uv run mes-server db upgrade                     # deja tu base local al día
uv run alembic -c packages/mes-server/alembic.ini revision --autogenerate -m "describe el cambio"
uv run mes-server db upgrade                     # aplica la nueva migración
```

Revisa siempre el archivo generado en `db/migrations/versions/` antes de confirmarlo: Alembic
no detecta todo (por ejemplo, renombrar una columna lo interpreta como borrar y crear). La prueba
`test_migrations_match_the_models` falla si el modelo y las migraciones no coinciden.

### Agregar una dependencia

```powershell
uv add --package mes-server <paquete>   # dependencia de un componente
uv add --dev <paquete>                  # herramienta de desarrollo
```

Confirma siempre el archivo `uv.lock` actualizado junto con el cambio.
