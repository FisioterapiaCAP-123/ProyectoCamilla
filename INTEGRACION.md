# Integración del panel de la camilla con el servidor

> **Nota del proyecto (29-10-2026):** el panel ya está integrado en `web/index.html` y `web/servidor.py`.
> No se usa WebSocket: los mismos mensajes van por HTTP (`POST /api/...` para mandar y `GET /api/estado`
> cada segundo para recibir), y Bootstrap está en `web/vendor/`. Cómo quedó: `GUIA.md`.
> Este documento queda como referencia de las reglas del control y de la seguridad del movimiento.

Este documento es el contrato entre el frontend (ya terminado) y el servidor
que corre en la Raspberry. El frontend no hay que tocarlo salvo en los cuatro
puntos marcados en la sección 1.

## Hay dos versiones del frontend y el contrato es el mismo

| Archivo | Qué es | Qué necesita al lado |
|---|---|---|
| `control-camilla.html` | Bootstrap solo para la rejilla, resto CSS propio | Nada, o Bootstrap por CDN |
| `control-camilla-bootstrap.html` | Bootstrap completo: tarjetas, modales, toasts, formularios | Carpeta `vendor/` |

Las dos tienen **exactamente la misma sección 8** en el script (el objeto
`SERVIDOR` y la función `recibir`), los mismos nombres de eventos y los mismos
payloads. Todo lo que dice este documento sirve igual para cualquiera de las
dos. Elegí una y borrá la otra.

Si usás `control-camilla-bootstrap.html`, la estructura en el servidor es:

```
control-camilla-bootstrap.html
vendor/
  bootstrap.min.css
  bootstrap.bundle.min.js
```

Bootstrap va servido en local a propósito: la camilla trabaja en red interna y
no debería depender de que la Raspberry tenga salida a internet. Si preferís el
CDN, en el `<head>` del archivo están las dos líneas alternativas comentadas.

---

## 1. Qué hay que tocar en el frontend

Todo está dentro del `<script>`, en la **sección 8**. No hace falta leer el
resto del archivo.

| Dónde | Qué es | Qué hacer |
|---|---|---|
| `var MODO_DEMO = true` | Interruptor de simulación | Ponerlo en `false` |
| `var API_BASE = ''` | Prefijo de las rutas HTTP | Dejar `''` si el HTML se sirve desde la misma Raspberry |
| `var WS_URL = ...` | URL del WebSocket | Ajustar si el socket no está en `/ws` |
| `var SERVIDOR = {...}` | Todo lo que el panel **manda** | Ya está escrito, no tocar |
| `function recibir(msg)` | Todo lo que el panel **recibe** | Ya está escrito, no tocar |

Con `MODO_DEMO = false` el panel deja de simular y empieza a hablar de verdad.

También hay que borrar dos bloques antes de producción, en cualquiera de las dos
versiones:

- El `<details id="simulador">` en el HTML.
- La **sección 8d** del script (el listener del simulador).

Y uno más, **solo en `control-camilla.html`**: el bloque de CSS marcado
`CAPA DE COMPATIBILIDAD BOOTSTRAP` al principio del `<style>`, que existe
únicamente para que la vista previa se vea bien sin el CSS de Bootstrap. Al
enlazar Bootstrap de verdad hay que borrarlo.

---

## 2. Rutas HTTP

### `POST /api/login`

Petición:

```json
{ "usuario": "Antonio", "clave": "..." }
```

Respuesta correcta:

```json
{
  "ok": true,
  "usuario": "Antonio",
  "control": { "titular": "Ana Lopez" }
}
```

`control.titular` es quien tiene el control **en este momento**, o `null` si no
lo tiene nadie. El panel lo usa para decidir si el que acaba de entrar toma el
control directamente o entra en solo lectura.

Respuesta incorrecta:

```json
{ "ok": false, "mensaje": "Usuario o contrasena incorrectos." }
```

El `mensaje` se muestra tal cual en la alerta roja del login. Si no viene, el
panel usa un texto genérico. No devolver detalles de por qué falló (si el
usuario no existe o si la clave está mal): eso ayuda a adivinar usuarios.

### `POST /api/logout`

Sin cuerpo. Cierra la sesión y, si ese usuario tenía el control, lo libera.

---

## 3. WebSocket

Un solo socket por dispositivo, autenticado con la sesión del login. Todos los
mensajes son JSON con un campo `tipo`.

### Del panel hacia el servidor

| Mensaje | Cuándo | Qué debe hacer el servidor |
|---|---|---|
| `{tipo:"mover", seccion, dir}` | Se aprieta y se mantiene un botón de altura | Arrancar ese motor en esa dirección |
| `{tipo:"detener", seccion}` | Se suelta el botón | Parar ese motor |
| `{tipo:"paso", seccion, grados}` | Cada grado de cabeza o piernas | Mover exactamente un grado |
| `{tipo:"paro", activo}` | Botón de paro | Cortar todo movimiento |
| `{tipo:"control:tomar"}` | Nadie tiene el control | Asignárselo a quien lo pide |
| `{tipo:"control:solicitar"}` | Pide el control a quien lo tiene | Avisar al titular |
| `{tipo:"control:cancelar"}` | Se arrepiente o se le acaba el tiempo | Anular la solicitud |
| `{tipo:"control:responder", id, aceptar}` | El titular decide | Transferir o no |
| `{tipo:"control:liberar"}` | Suelta el control voluntariamente | Dejarlo libre |

`seccion` es siempre `"altura"`, `"cabeza"` o `"piernas"`. `dir` es `1` o `-1`.

### Del servidor hacia el panel

| Mensaje | Cuándo mandarlo |
|---|---|
| `{tipo:"control", titular:"Ana"\|null}` | **A todos**, cada vez que cambia quien tiene el control |
| `{tipo:"control:solicitud", id:"abc123", usuario:"Ana"}` | Solo al titular, cuando alguien le pide el control |
| `{tipo:"control:respuesta", aceptada:true\|false, usuario:"Ana"}` | Solo al que pidió, con la decisión |
| `{tipo:"telemetria", cabeza:32, piernas:14}` | Cuando cambian los ángulos reales |
| `{tipo:"tope-altura", cual:"superior"\|"inferior"\|null}` | Cuando se pisa o se suelta un final de carrera |
| `{tipo:"paro", activo:true\|false}` | **A todos**, cuando cualquier dispositivo acciona el paro |

El `id` de la solicitud lo genera el servidor y vuelve tal cual en
`control:responder`. Sirve para no confundir dos solicitudes seguidas.

---

## 4. Reglas del control

Estas son las reglas que el servidor tiene que hacer cumplir. El frontend ya
las refleja, pero **la autoridad es el servidor**: un cliente modificado no
debe poder moverse sin permiso.

1. El control es de **una persona**, no de un dispositivo. Se identifica por el
   usuario del login.
2. Solo el titular puede mandar `mover`, `detener` y `paso`. Cualquier otro
   mensaje de movimiento se descarta en silencio.
3. **El paro de emergencia lo puede mandar cualquiera**, tenga el control o no,
   e incluso sin haber entrado. Esta es la única excepción y es deliberada.
4. Si no hay titular, el primero que lo pide se lo queda, sin preguntar a nadie.
5. Si hay titular, el que lo pide entra en solo lectura. Solo pasa a titular si
   el actual contesta que sí.
6. Una solicitud sin respuesta en 30 s se considera **denegada**. Nunca se
   transfiere el control por silencio.
7. Cuando el control cambia, el que lo pierde queda en solo lectura al instante
   y todos sus motores se paran.
8. Si el titular pierde la conexión, el servidor debe parar todos los motores y
   liberar el control pasado un tiempo corto. Una camilla no puede quedar
   bloqueada porque alguien cerró la tablet.

---

## 5. Seguridad del movimiento

Estas no son de interfaz, son del firmware, pero conviene que estén escritas.

- Los mensajes `mover` y `detener` van en pareja. Si el servidor deja de
  recibir señal del dispositivo que tiene un motor corriendo (watchdog de 1 s o
  menos), tiene que **parar el motor solo**. El botón funciona como interruptor
  de hombre muerto y esa garantía tiene que llegar hasta el motor, no quedarse
  en el navegador.
- Los finales de carrera se respetan en el firmware, no en el navegador. El
  panel deshabilita los botones al llegar al tope, pero eso es comodidad, no
  seguridad.
- El paro de emergencia debería cortar la alimentación de los motores por
  hardware, no solo por software.

---

## 6. Datos que el panel muestra y de dónde salen

| En pantalla | De dónde sale | Si no hay sensor |
|---|---|---|
| Ángulo de cabeza | `telemetria.cabeza` | El número sería inventado: no mostrarlo |
| Ángulo de piernas | `telemetria.piernas` | Igual |
| Altura | **No se muestra ningún número** | Correcto tal como está |
| Topes de altura | `tope-altura` (microswitches) | Es lo único medible sin encoder |

La barra de recorrido de la altura es una estimación para el dibujo. Se
recalibra sola cada vez que llega un `tope-altura`.

Si más adelante se le pone un potenciómetro o encoder lineal a la columna, en
el script hay que cambiar `CONFIG.altura` a `numerica: true` y vuelven a
aparecer la cifra en cm y el campo de "Ir a". Esa parte del código ya es
genérica.

---

## 7. Límites de recorrido

Están al principio del script, en `CONFIG`. Hay que ajustarlos a la mecánica
real antes de probar con un paciente:

```js
var CONFIG = {
  altura:  { min: 0,   max: 100, paso: 2, numerica: false, continua: true },
  cabeza:  { min: -30, max: 70,  paso: 1, numerica: true  },
  piernas: { min: 0,   max: 45,  paso: 1, numerica: true  }
};
```

Los rieles, los topes y la validación del campo "Ir a" se acomodan solos al
cambiar estos números.

---

## 8. Checklist de implementación

**Servidor**

- [ ] `POST /api/login` y `POST /api/logout`
- [ ] WebSocket en `/ws` autenticado con la sesión
- [ ] Máquina de estados del control (reglas de la sección 4)
- [ ] Watchdog que para los motores si se corta la señal
- [ ] Paro de emergencia aceptado de cualquier origen, siempre
- [ ] Emisión de `telemetria` y `tope-altura`

**Frontend**

- [ ] Elegir una de las dos versiones y borrar la otra
- [ ] Si es la versión Bootstrap: servir `vendor/` al lado del HTML
- [ ] Si es la otra: borrar la capa de compatibilidad Bootstrap del `<style>`
- [ ] `MODO_DEMO = false`
- [ ] Borrar el simulador (el `<details id="simulador">` y la sección 8d)
- [ ] Ajustar `CONFIG` a los límites reales de la mecánica
