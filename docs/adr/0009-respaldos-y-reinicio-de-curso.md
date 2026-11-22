# 0009. Respaldos y reinicio de curso

- **Estado:** Aceptado
- **Fecha:** 2026-11-22

## Contexto

El sistema lo usarán varias generaciones. Al terminar cada curso, el profesor debe dejar el
entorno limpio para la siguiente, sin perder la información del curso que termina y sin depender
de la terminal. Ver también el [ADR 0008](0008-desactivar-y-borrar-catalogos.md).

## Opciones consideradas

| Opción | Ventajas | Desventajas |
|---|---|---|
| Borrar registro por registro | No requiere desarrollo | Lento, propenso a errores, deja datos huérfanos |
| Una base de datos nueva por curso, desde la terminal | Trivial | Fuera de la aplicación; hay que recrear el catálogo base cada vez |
| Reinicio de curso en la aplicación, con respaldo automático y niveles | Lo hace el profesor desde el navegador, con seguridad y sin perder información | Más desarrollo |

Para los respaldos:

| Opción | Ventajas | Desventajas |
|---|---|---|
| Carpeta `respaldos/` en el servidor, con descarga desde la pantalla | Siempre hay copia aunque nadie la descargue; base para restaurar en el futuro | Ocupa disco en el servidor |
| Solo descarga al navegador | No ocupa disco | Si nadie descarga el archivo, se pierde el curso |

## Decisión

### Respaldos

- Se guardan en `respaldos/`, junto al archivo de la base de datos, o en la carpeta indicada por
  `MES_BACKUP_DIR`.
- Se hacen con la API de respaldo en línea de SQLite: la copia es consistente aunque el servidor
  esté en uso.
- Se escriben con un nombre temporal, se verifica su integridad (`PRAGMA integrity_check`) y solo
  entonces se renombran. Un respaldo fallido nunca deja un archivo que parezca válido.
- Junto a cada copia se guarda un **manifiesto** (`.json`) con: versión del formato, fecha,
  autor, motivo, revisión del esquema, versión de la aplicación y número de filas por tabla.
- Solo están disponibles cuando la base es un archivo SQLite.

### Reinicio de curso

| Nivel | Borra | Conserva |
|---|---|---|
| Producción | Órdenes, piezas, registros de ejecución y paros | Catálogos, recetas y usuarios |
| Producción y catálogos | Además productos (con su BOM), recetas y motivos de paro | Estaciones y usuarios |
| Todo | Además los usuarios que no son administradores | Estaciones y administradores |

- Siempre se hace un respaldo antes de borrar. Si el respaldo falla, no se borra nada.
- El borrado ocurre en una sola transacción.
- Hay que escribir `REINICIAR` para confirmar, y la pantalla muestra antes cuántos registros se
  borrarán.
- La acción queda en la **bitácora** (`audit_entries`), que nunca se borra. El autor se guarda
  como texto para que la entrada sobreviva aunque el usuario se elimine.
- Disponible también desde la terminal: `mes-server course reset --level ...`.

### Restauración

En esta fase **no se restaura desde la aplicación**. La estructura queda lista para hacerlo:

- El manifiesto indica la **revisión del esquema** de la copia, así que una copia vieja puede
  llevarse al esquema actual con las migraciones.
- Los **conteos por tabla** permiten verificar que la restauración quedó completa.
- `verify_backup` comprueba la integridad del archivo antes de usarlo.
- `find_backup` solo acepta nombres de archivo dentro de la carpeta de respaldos.

Mientras tanto, el procedimiento manual es:

1. Detener el servidor.
2. Guardar aparte el `mes.db` actual, por si hay que volver a él.
3. Copiar el respaldo elegido en lugar de `mes.db`.
4. Ejecutar `uv run mes-server db upgrade` para llevarlo al esquema actual.
5. Iniciar el servidor.

## Consecuencias

- La carpeta `respaldos/` crece con cada curso. El administrador puede descargar y borrar las
  copias antiguas desde el explorador de archivos.
- Se agrega la tabla `audit_entries` (migración 0002).
- Restaurar desde la aplicación se podrá agregar sin cambiar el formato de los respaldos.
