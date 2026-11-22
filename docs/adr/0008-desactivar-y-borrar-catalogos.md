# 0008. Desactivar y borrar registros de catálogo

- **Estado:** Aceptado
- **Fecha:** 2026-11-22

## Contexto

Los catálogos (productos, estaciones y motivos de paro) quedan referenciados por la historia de
producción: recetas, órdenes, registros de ejecución y paros. Borrar uno rompería la
trazabilidad, y la base de datos lo impide de todos modos por las claves foráneas.

Por otro lado, el sistema lo usarán varias generaciones de alumnos. Al terminar cada curso, el
profesor necesita dejar el entorno limpio para la siguiente generación, y durante el curso hay
que poder corregir errores de captura.

## Opciones consideradas

| Opción | Ventajas | Desventajas |
|---|---|---|
| Solo borrar | Simple | Rompe la historia o lo bloquea la base de datos |
| Solo desactivar | Conserva la historia | La base crece sin límite y los errores de captura no se pueden quitar |
| Desactivar para todos y borrar solo sin historia y solo el administrador; limpieza masiva con un reinicio de curso | Conserva la historia, permite corregir errores y limpiar entre cursos | Dos mecanismos que explicar |

## Decisión

| Acción | Ingeniero de procesos | Administrador |
|---|:-:|:-:|
| Crear y editar | ✓ | ✓ |
| Desactivar y reactivar | ✓ | ✓ |
| Borrar un registro **sin historia** | | ✓ |
| Borrar un registro **con historia** | | Solo mediante el reinicio de curso |

- Un registro desactivado no se ofrece para trabajo nuevo, pero conserva su historia.
- El **código** de un registro no cambia después de crearlo: es su identidad para el ERP y para
  la trazabilidad. Si se capturó mal y no tiene historia, el administrador lo borra y se vuelve a
  crear.
- Las **líneas del BOM** son parte de la definición del producto, no de la historia: quien
  mantiene productos puede agregarlas, editarlas y quitarlas.
- Se agrega el permiso `ADMINISTER_SYSTEM`, exclusivo del administrador, para borrar registros y,
  más adelante, reiniciar el curso.
- La regla se aplica en los servicios (`services/catalog.py`), no solo en las pantallas, para que
  también valga desde la terminal o la API.
- El **reinicio de curso**, con respaldo automático y tres niveles de limpieza, se implementa en
  la sección de Administración.

## Consecuencias

- Antes de borrar, la pantalla consulta qué registros dependen del elegido y, si hay alguno,
  explica por qué no se puede borrar y sugiere desactivarlo.
- Los errores de servicio llevan un código estable; la interfaz los traduce a español en
  `web/messages.py`.
