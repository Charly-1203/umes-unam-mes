# Arquitectura

## Contexto

Un MES ocupa el nivel 3 del modelo ISA-95: recibe del nivel empresarial (ERP) qué producir y
coordina, con el piso de producción (estaciones y PLC), cómo y cuándo se produce, registrando lo
que realmente ocurrió.

Este proyecto implementa el nivel 3 y la integración con el nivel 2. El ERP no se desarrolla: se
simula para mostrar la frontera entre niveles.

```
Nivel 4   ERP                 ──►  mes-erp-sim      (simulado)
Nivel 3   MES                 ──►  mes-server
Nivel 3/2 Estación de trabajo ──►  mes-gateway      (uno por estación)
Nivel 1-2 Control             ──►  PLC              (real o simulado)
```

## Componentes

### mes-server

Servidor central. Contiene la lógica del MES, la base de datos, la aplicación web y el servicio
de mensajería con las estaciones.

### mes-gateway

Servicio instalado en la computadora de cada estación. Ejecuta las recetas paso a paso contra el
PLC y reporta resultados al servidor. La comunicación con el PLC pasa por una **capa de drivers**
con una interfaz común, de modo que el mismo gateway funcione con un PLC simulado, Modbus TCP u
OPC UA.

La secuencia de la receta vive en el gateway; el PLC ejecuta operaciones atómicas con un
intercambio de señales estándar por paso (inicio, ocupado, terminado y resultado).

### mes-erp-sim

Emite órdenes de producción y listas de materiales hacia la API REST del servidor, como lo haría
un ERP real.

### mes-core

Contratos compartidos: esquemas de mensajes, enumeraciones y utilidades. Es la única pieza de
código que comparten los demás componentes.

## Comunicación

| Enlace | Protocolo | Motivo |
|---|---|---|
| ERP → MES | REST (HTTP/JSON) | Flujo transaccional, como en una integración ERP real |
| MES ↔ Gateway | MQTT | Publicación/suscripción; agregar estaciones no requiere cambiar el servidor y se detecta la desconexión de una estación |
| Gateway ↔ PLC | Modbus TCP u OPC UA | Depende del hardware del laboratorio |

## Tecnologías

| Elemento | Tecnología |
|---|---|
| Lenguaje | Python 3.13 |
| Interfaz web | NiceGUI |
| Gestión de paquetes y entorno | uv (workspace) |
| Calidad | Ruff, pytest, pre-commit |

Las tecnologías de persistencia, mensajería y comunicación con el PLC se registrarán como ADR al
incorporarse.

## Principios de diseño

1. **Esqueleto universal**: modelos genéricos (producto, receta, estación, orden) que no asumen
   un proceso específico.
2. **Simulación primero**: todo el flujo puede ejecutarse sin hardware.
3. **Componentes desacoplados**: cada componente se despliega por separado y se comunica por
   contratos definidos en `mes-core`.
4. **Visible para enseñar**: el flujo de información entre niveles debe poder observarse.
