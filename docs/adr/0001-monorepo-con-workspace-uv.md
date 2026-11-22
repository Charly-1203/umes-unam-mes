# 0001. Monorepo con workspace de uv

- **Estado:** Aceptado
- **Fecha:** 2026-11-16

## Contexto

El sistema tiene cuatro componentes que se despliegan por separado: el servidor, el gateway de
estación (uno por computadora), el simulador de ERP y los contratos compartidos. El servidor y
el gateway deben coincidir exactamente en el formato de los mensajes que intercambian. El equipo
es pequeño y el plazo es corto.

## Opciones consideradas

| Opción | Ventajas | Desventajas |
|---|---|---|
| Monorepo con workspace de uv | Un cambio de contrato y sus consumidores van en un mismo pull request; un solo entorno y una sola configuración de herramientas | Todo el historial vive en un repositorio |
| Repositorios separados | Independencia total entre componentes | Hay que versionar y publicar los contratos; un cambio exige varios pull requests coordinados |
| Un solo paquete | Lo más simple | El gateway arrastraría las dependencias del servidor (web y base de datos) a cada estación |

## Decisión

Un monorepo con un workspace de uv y cuatro paquetes independientes en `packages/`:
`mes-core`, `mes-server`, `mes-gateway` y `mes-erp-sim`.

## Consecuencias

- Cada componente declara solo sus propias dependencias, así que el gateway se instala ligero.
- Las reglas de dependencia (por ejemplo, el gateway no puede depender del servidor) se validan
  con pruebas.
- Si un paquete llega a reutilizarse fuera del proyecto, puede extraerse a su propio repositorio
  sin cambiar su código.
