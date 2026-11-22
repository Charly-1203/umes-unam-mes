# 0003. Idioma del código y la documentación

- **Estado:** Aceptado
- **Fecha:** 2026-11-16

## Contexto

El sistema se usará como material didáctico en un curso de la UNAM, pero también debe ser
mantenible a largo plazo y coherente con las librerías que utiliza, todas en inglés.

## Opciones consideradas

| Opción | Ventajas | Desventajas |
|---|---|---|
| Código en inglés, documentación en español | Código consistente con el ecosistema; documentación accesible para los alumnos | Dos idiomas en el repositorio |
| Todo en inglés | Un solo idioma | Menos accesible para el curso |
| Todo en español | Máxima accesibilidad | El código mezcla español con los nombres de las librerías |

## Decisión

Nombres, docstrings, comentarios y mensajes de error en inglés. README, guías, ADR y material
del curso en español.

## Consecuencias

- Las revisiones de código verifican el idioma correspondiente a cada tipo de archivo.
- Los términos técnicos en la documentación pueden conservarse en inglés cuando sea el uso
  habitual en la industria (por ejemplo, *downtime* o *gateway*).
