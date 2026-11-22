# mes-core

Contratos de dominio compartidos por todos los componentes del MES: esquemas de
mensajes, enumeraciones y utilidades.

## Reglas

- No depende de ningún otro paquete del workspace.
- No contiene infraestructura: nada de web, base de datos, cliente MQTT ni drivers de PLC.
- Todo lo que dos componentes necesiten acordar (por ejemplo, el formato de un mensaje)
  se define aquí una sola vez.

## Módulos

| Módulo | Contenido |
|---|---|
| `mes_core.enums` | Roles, estados de receta, orden y unidad, y resultado de un paso |
| `mes_core.lifecycle` | Transiciones de estado permitidas y su validación |
| `mes_core.limits` | Límites de aceptación de parámetros y evaluación OK/NOK |
| `mes_core.clock` | Hora actual en UTC |

```python
from mes_core.limits import ParameterLimit, evaluate_all

limits = [ParameterLimit("torque", minimum=5.0, maximum=7.0, unit="N·m")]
evaluate_all(limits, {"torque": 6.2})  # StepResult.OK
```
