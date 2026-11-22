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

## Acceso y pantallas

| Módulo | Contenido |
|---|---|
| `mes_server.auth` | Hash y verificación de contraseñas (Argon2id) |
| `mes_server.services.users` | Alta de usuarios, validaciones e inicio de sesión |
| `mes_server.web.app` | Página raíz: decide entre inicio de sesión y la aplicación |
| `mes_server.web.navigation` | Secciones, su permiso requerido y nombres de los roles |
| `mes_server.web.pages` | Pantallas: inicio de sesión, marco común, inicio y secciones |
| `mes_server.web.session` | Usuario con sesión iniciada en el navegador |
| `mes_server.web.theme` | Paleta, archivos estáticos y escudos institucionales |
| `mes_server/web/static` | Hoja de estilos, tipografía Inter y carpeta de escudos |

## Ejecución

```powershell
uv run mes-server --version
uv run mes-server db upgrade    # crea o actualiza el esquema
uv run mes-server db status     # muestra la revisión aplicada y la más reciente
uv run mes-server users create-admin
uv run mes-server serve         # http://127.0.0.1:8080
```
