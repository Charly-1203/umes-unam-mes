# mes-gateway

Gateway de estación: se instala en la computadora de cada estación de trabajo.

## Responsabilidades

- Recibir del servidor la orden activa y su receta.
- Ejecutar los pasos de la receta contra el PLC mediante una capa de drivers
  (simulado, Modbus TCP u OPC UA).
- Reportar resultados, estados y downtime al servidor.
- Mostrar la pantalla del operador.

## Regla clave

No depende de `mes-server`: se instala y se ejecuta de forma independiente en cada
estación y solo se comunica con el servidor por mensajes.

## Ejecución

```powershell
uv run mes-gateway --version
```
