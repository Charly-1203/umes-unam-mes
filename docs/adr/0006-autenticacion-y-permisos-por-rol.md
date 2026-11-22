# 0006. Autenticación y permisos por rol

- **Estado:** Aceptado
- **Fecha:** 2026-11-21

## Contexto

El MES tiene cuatro tipos de usuario (administrador, ingeniero de procesos, supervisor y
operador) que deben ver y hacer cosas distintas. Las contraseñas deben guardarse de forma segura
y el sistema necesita un primer administrador sin depender de credenciales por defecto.

## Opciones consideradas

### Almacenamiento de contraseñas

| Opción | Ventajas | Desventajas |
|---|---|---|
| Argon2id (`pwdlib`) | Algoritmo recomendado por OWASP; resistente a ataques con GPU | Dependencia nativa (`argon2-cffi`), con binarios para Windows y Linux |
| bcrypt | Muy difundido | Limita la contraseña a 72 bytes; menos resistente que Argon2 |

### Primer administrador

| Opción | Ventajas | Desventajas |
|---|---|---|
| Comando `mes-server users create-admin` | Sin contraseñas por defecto; la contraseña nunca queda en el código | Requiere un paso en la terminal |
| Usuario `admin/admin` creado automáticamente | Arranque inmediato | Riesgo de que nunca se cambie |

### Control de acceso

| Opción | Ventajas | Desventajas |
|---|---|---|
| Permisos asignados a roles | Las pantallas preguntan por una capacidad; cambiar un rol es editar una tabla | Un nivel más de indirección |
| Revisar el rol directamente en cada pantalla | Simple al inicio | Cambiar lo que hace un rol obliga a tocar muchas pantallas |

## Decisión

- Contraseñas con **Argon2id** mediante `pwdlib`. Los hashes con parámetros antiguos se
  actualizan solos cuando el usuario inicia sesión.
- Primer administrador con **`mes-server users create-admin`**. La pantalla de inicio de sesión
  muestra cómo hacerlo mientras no exista ninguno.
- **Permisos por rol** definidos en `mes_core.permissions`:

| Permiso | Administrador | Ingeniero de procesos | Supervisor | Operador |
|---|:-:|:-:|:-:|:-:|
| Gestionar usuarios | ✓ | | | |
| Gestionar productos, estaciones y recetas | ✓ | ✓ | | |
| Gestionar órdenes de trabajo | ✓ | | ✓ | |
| Ver producción, downtime y trazabilidad | ✓ | ✓ | ✓ | |
| Reportar downtime | ✓ | | ✓ | ✓ |
| Operar una estación | ✓ | | | ✓ |

- La sesión del navegador guarda solo el identificador del usuario. El usuario se vuelve a leer
  de la base de datos en cada página, así que desactivarlo o cambiar su rol surte efecto de
  inmediato.

## Consecuencias

- La cookie de sesión se firma con `MES_STORAGE_SECRET`. Si no se define, se genera una al
  arrancar y todos los usuarios deben volver a iniciar sesión tras cada reinicio.
- El operador no tiene secciones en el servidor: su trabajo se hace en la pantalla del gateway
  de su estación.
- Un intento fallido tarda lo mismo exista o no el usuario, para no revelar nombres válidos.
