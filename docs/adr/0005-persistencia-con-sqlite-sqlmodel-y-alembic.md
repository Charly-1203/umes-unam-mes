# 0005. Persistencia con SQLite, SQLModel y Alembic

- **Estado:** Aceptado
- **Fecha:** 2026-11-21

## Contexto

El servidor necesita guardar usuarios, productos, recetas, órdenes, piezas, registros de
ejecución y paros. El sistema corre en una computadora del laboratorio, con pocas estaciones
escribiendo a la vez, y debe instalarse sin depender de un servidor de base de datos. El esquema
cambiará conforme se agreguen funcionalidades.

## Opciones consideradas

### Motor de base de datos

| Opción | Ventajas | Desventajas |
|---|---|---|
| SQLite | Sin instalación; un solo archivo fácil de respaldar o reiniciar en clase | Escrituras concurrentes limitadas |
| PostgreSQL | Robusto ante muchas escrituras simultáneas; estándar industrial | Requiere instalar y administrar un servidor o usar Docker |

### Acceso a datos

| Opción | Ventajas | Desventajas |
|---|---|---|
| SQLModel | Modelos con anotaciones de tipo; comparte base con Pydantic, que se usará en los contratos de mensajes | Proyecto más joven que SQLAlchemy |
| SQLAlchemy directo | El estándar más maduro | Más código repetitivo para lo mismo |

## Decisión

- **SQLite** como base de datos por defecto, mediante la URL `sqlite:///mes.db`.
- **SQLModel** (sobre SQLAlchemy) para el modelo de datos.
- **Alembic** para las migraciones del esquema, aplicadas con `mes-server db upgrade`.
- La URL se configura con la variable `MES_DATABASE_URL`, de modo que cambiar a PostgreSQL no
  requiere modificar código.

## Consecuencias

- El código evita funciones exclusivas de un motor, y las restricciones tienen nombres
  deterministas para que las migraciones sean portables.
- Las claves foráneas se activan explícitamente en SQLite, que las desactiva por defecto.
- Todo cambio en los modelos requiere una migración. Una prueba falla si el modelo y las
  migraciones no coinciden.
- Si el número de estaciones crece y aparecen bloqueos de escritura, basta con cambiar la URL a
  PostgreSQL y ejecutar las migraciones.
