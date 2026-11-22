# 0007. Identidad visual

- **Estado:** Aceptado
- **Fecha:** 2026-11-21

## Contexto

La primera versión de las pantallas usaba el estilo por defecto de NiceGUI. Se busca una
interfaz moderna que use los colores institucionales de la UNAM, que funcione en computadoras
y celulares, y que no dependa de internet, porque la red del laboratorio puede estar aislada.

Se exploraron tres direcciones visuales sobre las mismas pantallas (inicio de sesión e inicio):

| Dirección | Descripción | Resultado |
|---|---|---|
| A · Institucional claro | Banda azul con línea oro y tarjetas blancas | Descartada: demasiado conservadora |
| B · Barra lateral azul | Menú lateral azul UNAM, contenido claro, inicio de sesión dividido con la pirámide ISA-95 | **Elegida para el servidor** |
| C · Planta (modo oscuro) | Fondo azul oscuro con acentos oro, alto contraste | Reservada para la pantalla del operador en el gateway |

## Decisión

- **Dirección B** para la aplicación web del servidor.
- **Paleta** tomada del manual de identidad gráfica de la UNAM:

| Color | HEX | Pantone | Uso |
|---|---|---|---|
| Azul UNAM | `#013B75` | 540 | Menú, botones, íconos y títulos |
| Oro UNAM | `#D9A500` | 117 | Acentos: indicador de sección activa, barras y avatar |

  El oro no alcanza el contraste mínimo como texto sobre blanco, así que solo se usa en acentos.
  Para textos de aviso se usa un oro oscuro (`#7A5A00`).
- **Tipografía Inter**, incluida en el servidor (licencia SIL Open Font License) para que se vea
  igual sin conexión a internet.
- **Estilos centralizados** en `static/css/theme.css` con variables CSS (`--mes-*`) y clases
  `mes-*`. Las pantallas usan esas clases en lugar de estilos sueltos.
- **Escudos configurables**: cada instalación coloca los archivos oficiales en
  `static/branding/`. Mientras no existan se muestra un ícono genérico; el repositorio no
  incluye escudos.

## Consecuencias

- Cambiar un color o un espaciado se hace en un solo archivo.
- La pantalla de inicio de sesión también enseña: muestra la pirámide ISA-95 con el MES resaltado.
- Si el laboratorio pertenece a una dependencia con su propio manual, los valores de la paleta
  pueden ajustarse en `theme.css` y `theme.py` sin tocar las pantallas.
- El modo oscuro de la dirección C se implementará con el gateway.
