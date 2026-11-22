# 0002. Interfaz web con NiceGUI

- **Estado:** Aceptado
- **Fecha:** 2026-11-16

## Contexto

El MES necesita pantallas para ingeniería, supervisión, administración y para el operador en
cada estación. Varias de ellas, como los estados de producción y el downtime, deben actualizarse
en tiempo real. El equipo tiene experiencia principalmente en desarrollo backend con Python y
C#, y el plazo es de aproximadamente tres meses.

## Opciones consideradas

| Opción | Ventajas | Desventajas | Curva de aprendizaje |
|---|---|---|---|
| NiceGUI | Interfaz escrita en Python; actualización en tiempo real integrada; corre sobre FastAPI | Menos control fino del diseño visual; ecosistema más joven | Baja |
| FastAPI + Jinja + HTMX | Tecnologías web estándar; control total del diseño | Requiere HTML, CSS y el modelo de HTMX; el tiempo real se construye a mano | Media |
| React u otro framework de frontend | Máxima flexibilidad | Segundo lenguaje y segundo proyecto de compilación | Alta |

## Decisión

NiceGUI para todas las pantallas, tanto del servidor como del gateway.

## Consecuencias

- Todo el sistema se desarrolla en un solo lenguaje.
- El tiempo real no requiere infraestructura adicional.
- La versión de NiceGUI se fija en `uv.lock` para evitar cambios inesperados.
- La lógica de negocio se mantiene fuera de las pantallas, de modo que la interfaz pueda
  sustituirse en el futuro sin reescribir el MES.
