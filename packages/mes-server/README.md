# mes-server

Servidor central del MES (nivel 3 de ISA-95).

## Responsabilidades

- Aplicación web: login, catálogos, recetas, órdenes, estados, downtime y trazabilidad.
- API REST que recibe órdenes y BOM del ERP simulado.
- Persistencia de datos.
- Servicio de mensajería que despacha trabajo a los gateways y recibe sus eventos.

## Ejecución

```powershell
uv run mes-server --version
```
