# mes-server

Servidor central del MES (nivel 3 de ISA-95).

## Responsabilidades

- Aplicación web: login, catálogos, recetas, órdenes, estados, downtime y trazabilidad.
- API REST que recibe órdenes y BOM del ERP simulado.
- Persistencia de datos.
- Servicio de mensajería que despacha trabajo a los gateways y recibe sus eventos.

## Persistencia

| Módulo | Contenido |
|---|---|
| `mes_server.config` | Configuración desde variables de entorno (`MES_DATABASE_URL`) |
| `mes_server.db.models` | Modelo de datos; ver [docs/modelo-de-datos.md](../../docs/modelo-de-datos.md) |
| `mes_server.db.engine` | Creación del motor y sesiones transaccionales |
| `mes_server.db.migrate` | Aplicación de migraciones desde código |
| `mes_server.db.migrations` | Migraciones de Alembic |

## Ejecución

```powershell
uv run mes-server --version
uv run mes-server db upgrade    # crea o actualiza el esquema
uv run mes-server db status     # muestra la revisión aplicada y la más reciente
```
