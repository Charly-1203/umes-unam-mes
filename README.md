# UNAM-MES

Sistema de Ejecución de Manufactura (MES) didáctico para el Laboratorio de Automatización de la
Universidad Nacional Autónoma de México.

El objetivo no es competir con un MES comercial, sino ofrecer un **esqueleto universal, mínimo y
funcional** que muestre qué es un MES y cómo se integra con los demás niveles de una planta
(ERP, estaciones de trabajo y PLC), y que pueda ampliarse con el tiempo.

## Alcance funcional

| Funcionalidad | Descripción |
|---|---|
| Login y roles | Administrador, ingeniero de procesos, supervisor y operador |
| Gestión de recetas | Pasos ordenados, parámetros, límites OK/NOK y versión |
| Órdenes de producción | Recepción desde el ERP simulado, liberación y asignación a estación |
| Ejecución de órdenes | El gateway ejecuta la receta paso a paso contra el PLC |
| Interlock entre estaciones | Bloquea una pieza que no completó los pasos previos, si la receta lo pide |
| Estados de producción | Estado de órdenes y estaciones en tiempo real |
| Downtime | Detección de paros y registro del motivo |
| Trazabilidad | Historial por número de serie u orden |

## Arquitectura

```
[ERP simulado] --REST--> [Servidor MES] <--MQTT--> [Gateway de estación] <--Modbus/OPC UA--> [PLC]
   nivel 4                  nivel 3                    nivel 3 / 2                          niveles 1-2
```

El detalle está en [docs/arquitectura.md](docs/arquitectura.md), el modelo de datos en
[docs/modelo-de-datos.md](docs/modelo-de-datos.md) y las decisiones de diseño en
[docs/adr](docs/adr).

## Estructura del repositorio

```
unam-mes/
├── packages/
│   ├── mes-core/      # Contratos compartidos: mensajes, enumeraciones, utilidades
│   ├── mes-server/    # Servidor MES: aplicación web, API REST, persistencia, mensajería
│   ├── mes-gateway/   # Gateway de estación: ejecución de recetas contra el PLC
│   └── mes-erp-sim/   # Simulador de ERP: envía órdenes y BOM al servidor
├── docs/              # Arquitectura y registros de decisiones (ADR)
└── pyproject.toml     # Raíz del workspace de uv y configuración de herramientas
```

Cada paquete se encuentra en `packages/<nombre>/src/<modulo>` y sus pruebas en
`packages/<nombre>/tests`.

## Requisitos

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Git

## Instalación

```powershell
git clone <url-del-repositorio>
cd unam-mes
uv sync
uv run pre-commit install --install-hooks
```

`uv sync` crea el entorno virtual `.venv` e instala los cuatro paquetes en modo editable junto con
las herramientas de desarrollo.

## Primer arranque

```powershell
uv run mes-server db upgrade         # crea mes.db con el esquema actual
uv run mes-server users create-admin # pide la contraseña del usuario "admin"
uv run mes-server serve              # abre http://127.0.0.1:8080
```

Para probar los distintos roles, crea más usuarios:

```powershell
uv run mes-server users create --username ingeniero --full-name "Ingeniera Demo" --role process_engineer
uv run mes-server users create --username supervisor --full-name "Supervisor Demo" --role supervisor
uv run mes-server users list
```

Roles disponibles: `admin`, `process_engineer`, `supervisor` y `operator`.

## Configuración

El servidor se configura con variables de entorno:

| Variable | Valor por defecto | Uso |
|---|---|---|
| `MES_DATABASE_URL` | `sqlite:///mes.db` | Base de datos (URL de SQLAlchemy) |
| `MES_HOST` | `127.0.0.1` | Dirección de escucha; usa `0.0.0.0` para aceptar conexiones de otras computadoras del laboratorio |
| `MES_PORT` | `8080` | Puerto del servidor web |
| `MES_STORAGE_SECRET` | aleatorio en cada arranque | Firma la cookie de sesión; defínelo para que los usuarios no pierdan la sesión al reiniciar |
| `MES_BACKUP_DIR` | `respaldos` junto a `mes.db` | Carpeta de respaldos |

Ejemplo en PowerShell:

```powershell
$env:MES_HOST = "0.0.0.0"
$env:MES_STORAGE_SECRET = "una-cadena-larga-y-dificil-de-adivinar"
uv run mes-server serve
```

## Fin de curso: respaldos y reinicio

Al terminar un curso, el administrador entra a **Administración** y elige un nivel de reinicio:

| Nivel | Borra | Conserva |
|---|---|---|
| Producción | Órdenes, piezas, registros de ejecución y paros | Catálogos, recetas y usuarios |
| Producción y catálogos | Además productos, recetas y motivos de paro | Estaciones y usuarios |
| Todo | Además los usuarios que no son administradores | Estaciones y administradores |

Antes de borrar se crea un respaldo en `respaldos/`, que se puede descargar desde la misma
pantalla. Lo mismo desde la terminal:

```powershell
uv run mes-server backup create
uv run mes-server backup list
uv run mes-server course reset --level production
```

Para restaurar un respaldo (todavía no disponible desde la aplicación):

1. Detén el servidor y guarda aparte el `mes.db` actual.
2. Copia el respaldo elegido en lugar de `mes.db`.
3. Ejecuta `uv run mes-server db upgrade` e inicia el servidor.

Detalles en el [ADR 0009](docs/adr/0009-respaldos-y-reinicio-de-curso.md).

## Escudos institucionales

El repositorio no incluye escudos. Para mostrarlos, coloca los archivos oficiales en
`packages/mes-server/src/mes_server/web/static/branding/`:

| Archivo | Dónde aparece |
|---|---|
| `escudo-unam.svg` | Menú lateral y pantalla de inicio de sesión |
| `escudo-dependencia.svg` | Pantalla de inicio de sesión |

Mientras no existan, la aplicación muestra un ícono genérico.

## Comandos frecuentes

| Acción | Comando |
|---|---|
| Ejecutar las pruebas | `uv run pytest` |
| Pruebas con cobertura | `uv run pytest --cov` |
| Revisar estilo | `uv run ruff check .` |
| Dar formato | `uv run ruff format .` |
| Ejecutar todas las verificaciones | `uv run pre-commit run --all-files` |
| Iniciar el servidor web | `uv run mes-server serve` |
| Crear o actualizar la base de datos | `uv run mes-server db upgrade` |
| Ver la versión del esquema | `uv run mes-server db status` |
| Crear el primer administrador | `uv run mes-server users create-admin` |
| Listar usuarios | `uv run mes-server users list` |
| Crear un respaldo | `uv run mes-server backup create` |
| Reiniciar el curso | `uv run mes-server course reset --level production` |
| Versión de cada componente | `uv run mes-server --version`, `uv run mes-gateway --version`, `uv run mes-erp-sim --version` |

## Estado

| Etapa | Contenido | Estado |
|---|---|---|
| Estructura | Monorepo, herramientas de calidad y pruebas base | Listo |
| Modelo de dominio | Estados, ciclos de vida, límites, modelo de datos y migraciones | Listo |
| Acceso | Inicio de sesión, roles, permisos y menú por rol | Listo |
| Identidad visual | Paleta UNAM, tipografía, menú lateral y pantallas responsivas | Listo |
| Catálogos | Productos con lista de materiales, estaciones y motivos de paro | Listo |
| Administración | Usuarios, respaldos, reinicio de curso y bitácora | Listo |

Las funcionalidades se incorporan por etapas; consulta [CONTRIBUTING.md](CONTRIBUTING.md) para
el flujo de trabajo.
