# mes-core

Contratos de dominio compartidos por todos los componentes del MES: esquemas de
mensajes, enumeraciones y utilidades.

## Reglas

- No depende de ningún otro paquete del workspace.
- No contiene infraestructura: nada de web, base de datos, cliente MQTT ni drivers de PLC.
- Todo lo que dos componentes necesiten acordar (por ejemplo, el formato de un mensaje)
  se define aquí una sola vez.
