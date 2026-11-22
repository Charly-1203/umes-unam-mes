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

El detalle está en [docs/arquitectura.md](docs/arquitectura.md) y las decisiones de diseño en
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

## Comandos frecuentes

| Acción | Comando |
|---|---|
| Ejecutar las pruebas | `uv run pytest` |
| Pruebas con cobertura | `uv run pytest --cov` |
| Revisar estilo | `uv run ruff check .` |
| Dar formato | `uv run ruff format .` |
| Ejecutar todas las verificaciones | `uv run pre-commit run --all-files` |
| Versión de cada componente | `uv run mes-server --version`, `uv run mes-gateway --version`, `uv run mes-erp-sim --version` |

## Estado

Versión `0.1.0`: estructura del repositorio, herramientas de calidad y pruebas base. Las
funcionalidades se incorporan por etapas; consulta [CONTRIBUTING.md](CONTRIBUTING.md) para el
flujo de trabajo.
