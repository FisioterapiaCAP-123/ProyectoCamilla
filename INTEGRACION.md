# Proyecto Camilla: especificación de integración

**Última actualización:** 08-11-2026  
**Guía general:** [GUIA.md](GUIA.md)

Este documento describe cómo se comunican el panel web (`web/plantillas/` y `web/publico/`), el servidor (`web/servidor.py`) y la base de datos (`web/basedatos.py`), tal como están implementados. Es la referencia para modificar cualquiera de esas partes.

## Contenido

1. [Modelo de comunicación](#1-modelo-de-comunicación)
2. [Convenciones de la API](#2-convenciones-de-la-api)
3. [Referencia de la API](#3-referencia-de-la-api)
4. [Reglas del control](#4-reglas-del-control)
5. [Seguridad del movimiento](#5-seguridad-del-movimiento)
6. [Posición y telemetría](#6-posición-y-telemetría)
7. [Parámetros](#7-parámetros)
8. [Integración con el hardware](#8-integración-con-el-hardware)
9. [Base de datos](#9-base-de-datos)
10. [Estructura del panel web](#10-estructura-del-panel-web)
11. [Comportamientos a tener en cuenta](#11-comportamientos-a-tener-en-cuenta)

## 1. Modelo de comunicación

```text
Panel (publico/js/)                           Servidor (servidor.py)

SERVIDOR.*, ADMIN.*  ---- POST /api/... ---->  do_POST --> Camilla, administrar()
consultar() cada 1 s ---- GET /api/estado -->  do_GET  --> Camilla.estado()
recibir()            <--- JSON --------------

                                               Hilo vigilar() cada 0.5 s
                                               basedatos.py --> camilla.db
```

| Aspecto | Implementación |
|---|---|
| Protocolo | HTTP/1.0 sin cifrar, puerto 8000, en todas las interfaces. No se usa WebSocket. |
| Servidor | `ThreadingHTTPServer` de la biblioteca estándar: un hilo por conexión. Cada petición usa su propia conexión TCP. |
| Estado compartido | Una instancia de la clase `Camilla`, protegida por `candado` (`threading.Lock`). |
| Trabajo fuera del candado | Cálculo de contraseñas y accesos a SQLite. |
| Vigilancia | El hilo `vigilar()` revisa cada 0.5 s el hombre muerto, el titular sin conexión, los pedidos vencidos y las sesiones viejas. |
| Recepción en la página | Consulta cada 1 s, con una sola consulta en curso por página. Tras una orden de control se consulta de inmediato. |

## 2. Convenciones de la API

| Elemento | Regla |
|---|---|
| URL base | La misma de la página (`API_BASE = ''`). |
| Cuerpo de `POST` | Objeto JSON de hasta 4096 bytes. Un cuerpo vacío equivale a `{}`. |
| Sesión | Cabecera `X-Sesion` con el token entregado por `login` o `registro`. |
| Respuestas JSON | `application/json; charset=utf-8` con `Cache-Control: no-store`. |
| Errores de negocio | HTTP 200 con `"ok": false`. El `mensaje`, cuando existe, se muestra al usuario. |

| Código | Significado |
|---|---|
| 200 | Petición procesada. El resultado se lee en `ok`. |
| 302 | Redirección del portal cautivo. Solo en `GET`. |
| 400 | Cuerpo inválido: JSON mal formado, no es un objeto o supera 4096 bytes. Responde `{"ok": false, "mensaje": "Peticion invalida."}`. |
| 401 | Ruta `POST` sin sesión válida, incluidas las rutas inexistentes. Mensaje: `Tu sesión terminó. Vuelve a iniciar sesión.` |
| 403 | Ruta de administración con una sesión que no es de administrador. Mensaje: `Solo un administrador puede entrar aquí.` |
| 404 | Ruta inexistente. Responde el texto plano `No encontrado`. |

| Acceso | Rutas |
|---|---|
| Sin sesión | `GET /`, `GET /css/*`, `GET /js/*`, `GET /vendor/*`, `GET /api/estado`, `POST /api/login`, `POST /api/registro`, `POST /api/paro` |
| Con sesión | `POST /api/logout`, `POST /api/control/*`, `POST /api/mover`, `POST /api/detener`, `POST /api/paso` |
| Administrador | `POST /api/pacientes/*`, `POST /api/usuarios/*` |

## 3. Referencia de la API

### 3.1 Archivos estáticos

Las atiende `web/paginas.py`, que lee del disco en cada petición.

- `GET /` entrega `plantillas/index.html` con sus parciales ya insertados. El navegador recibe un solo documento HTML.
- Cualquier otra ruta se busca dentro de `web/publico/`. Solo se entregan archivos `.css`, `.js` y `.woff2`; lo demás responde 404. Una ruta que intente salir de esa carpeta también responde 404, de modo que `camilla.db`, el código Python y las plantillas no son accesibles.

### 3.2 Portal cautivo

Si una petición `GET` llega por la dirección `10.42.0.1` con una cabecera `Host` distinta de `10.42.0.1`, el servidor responde `302` hacia `http://10.42.0.1:8000/`. El procedimiento completo está en [Portal cautivo](GUIA.md#84-portal-cautivo).

### 3.3 Estado

`GET /api/estado`, con cabecera `X-Sesion` opcional.

```json
{
  "usuario": "antonio",
  "nombre": "Antonio",
  "rol": "admin",
  "control": { "titular": "Ana", "usuario": "ana" },
  "paro": false,
  "simulacion": true,
  "solicitud": null,
  "respuesta": null,
  "telemetria": { "cabeza": 0, "piernas": 0 }
}
```

| Campo | Contenido |
|---|---|
| `usuario`, `nombre`, `rol` | Perfil de la sesión. Son `null` sin sesión válida; con el panel abierto, la página lo interpreta como sesión terminada. |
| `control.titular` | Nombre para mostrar del titular, o `null`. |
| `control.usuario` | Usuario del titular, o `null`. |
| `paro` | Estado del paro de emergencia. |
| `simulacion` | Valor de `SIMULACION`. La página no lo usa. |
| `solicitud` | Pedido pendiente `{id, usuario}`. Solo le llega al titular. `usuario` contiene el nombre para mostrar de quien pide. |
| `respuesta` | Decisión `{aceptada, usuario}`. Solo le llega a quien pidió y se entrega una vez. `usuario` contiene el nombre para mostrar del titular que decidió o soltó el control. |
| `telemetria` | Ángulos `{cabeza, piernas}` en grados enteros. |

Sin sesión, la respuesta incluye igualmente `control`, `paro`, `simulacion` y `telemetria`. Cada consulta con token válido actualiza el último contacto de esa sesión.

### 3.4 Sesión

**`POST /api/login`**

```json
{ "usuario": "antonio", "clave": "abc123" }
```

Respuesta correcta:

```json
{
  "ok": true,
  "sesion": "<token>",
  "usuario": "antonio",
  "nombre": "Antonio",
  "rol": "admin",
  "control": { "titular": null, "usuario": null }
}
```

| Caso | `mensaje` |
|---|---|
| Usuario o clave vacíos | `Escribe tu usuario y tu contraseña.` |
| Usuario o clave incorrectos; responde tras 1 s adicional | `Usuario o contraseña incorrectos.` |
| Perfil desactivado | `Tu perfil está desactivado. Habla con el administrador.` |

**`POST /api/registro`**, con cuerpo `{usuario, nombre, clave}`. Crea un perfil con rol `fisio` y abre su sesión. La respuesta correcta es igual a la de `login`. Un error responde `{"ok": false, "campo": "nombre" o "usuario" o "clave", "mensaje": "..."}`. Las reglas de cada campo están en [Validación](#validación).

**`POST /api/logout`**, sin cuerpo. Cierra la sesión y libera el control si la sesión era del titular. Responde `{"ok": true, "mensaje": null}`.

**Ciclo de vida de la sesión**

1. `login` o `registro` entregan un token generado con `secrets.token_urlsafe(24)`.
2. La página lo guarda en `sessionStorage` con la clave `sesion` y lo envía en `X-Sesion`.
3. Al recargar, la página consulta `/api/estado` con el token guardado. Si llega `usuario`, vuelve al panel; si no, borra el token.
4. La sesión termina por `logout`, por un nuevo inicio de sesión del mismo perfil, por desactivar o borrar el perfil, por 12 horas sin uso o por reiniciar el servidor.

### 3.5 Control

Todas requieren sesión y responden `{"ok": true o false, "mensaje": texto o null}`.

| Ruta | Cuerpo | Efecto | Mensajes con `ok: false` |
|---|---|---|---|
| `/api/control/tomar` | Ninguno | Asigna el control si está libre o ya es del solicitante. | `<Nombre> ya tiene el control.` |
| `/api/control/solicitar` | Ninguno | Si está libre, equivale a `tomar`. Si está ocupado, crea el pedido pendiente. | `<Nombre> ya pidió el control. Intenta en unos segundos.` |
| `/api/control/cancelar` | Ninguno | Anula el pedido de esta sesión. | Ninguno |
| `/api/control/responder` | `{id, aceptar}` | El titular acepta o rechaza. `aceptar` solo cuenta como sí con el valor exacto `true`. | `No tienes el control.`, `Esa solicitud ya no está vigente.` |
| `/api/control/liberar` | Ninguno | Si el solicitante es titular, libera el control o lo pasa a quien lo pidió. | Ninguno |

### 3.6 Movimiento

Todas requieren sesión.

| Ruta | Cuerpo | Efecto | Uso desde la página |
|---|---|---|---|
| `/api/mover` | `{seccion, dir}` | Registra un motor continuo en marcha y renueva su señal. | Solo altura. Se repite cada 400 ms mientras el botón está pulsado. |
| `/api/detener` | `{seccion}` | Para el motor en marcha si es de esa sección. | Al soltar cualquier botón de movimiento. |
| `/api/paso` | `{seccion, grados}` | Ajusta el ángulo simulado un grado, dentro de `LIMITES`. | Cabeza y piernas. También lo usan "Ir a" y "Plano 0°". |

- `seccion` debe ser `altura`, `cabeza` o `piernas`. `dir` y `grados` deben ser el entero `1` o `-1`.
- `/api/paso` solo acepta `cabeza` y `piernas`.
- Una orden inválida o de alguien que no puede mover se descarta y responde `{"ok": false, "mensaje": null}`.
- `/api/paso` en un límite responde `ok: true` sin cambiar el ángulo.
- `/api/detener` responde siempre `ok: true` y solo actúa si el solicitante es titular y no hay paro.

### 3.7 Paro de emergencia

**`POST /api/paro`**, con cuerpo `{"activo": true}` para activar y `{"activo": false}` para liberar. No requiere sesión y responde `{"ok": true, "mensaje": null}`.

- `activo` solo cuenta como activar con el valor exacto `true`. Si falta o tiene otro valor, el paro se libera.
- Al activarse se llama a `parar_motores`.
- El evento se anota con el usuario de la sesión o, sin sesión, con la IP de origen.

### 3.8 Registros de pacientes

Rol administrador.

| Ruta | Cuerpo | Respuesta correcta |
|---|---|---|
| `/api/pacientes/lista` | `{}` | `{"ok": true, "pacientes": [{id, nombre, edad, creado, creado_por}]}`, del más reciente al más antiguo |
| `/api/pacientes/guardar` | `{id, nombre, edad}`; `id: null` crea uno nuevo | `{"ok": true, "id": n}` |
| `/api/pacientes/borrar` | `{id}` | `{"ok": true}` |

| Caso | Respuesta con `ok: false` |
|---|---|
| `id` no entero al guardar | `mensaje`: `Petición inválida.` |
| Nombre con menos de 2 caracteres | `campo: "nombre"`, `mensaje`: `Escribe el nombre del paciente.` |
| Edad inválida | `campo: "edad"`, `mensaje`: `La edad debe ser un número entre 0 y 120.` |
| El registro no existe | `mensaje`: `Ese registro ya no existe.` |

El nombre se normaliza quitando espacios repetidos y se corta a 80 caracteres. Editar un registro no cambia `creado` ni `creado_por`.

### 3.9 Perfiles de usuario

Rol administrador.

| Ruta | Cuerpo | Efecto |
|---|---|---|
| `/api/usuarios/lista` | `{}` | `{"ok": true, "usuarios": [{id, usuario, nombre, rol, activo, creado}]}`, ordenados por nombre |
| `/api/usuarios/rol` | `{id, rol}` | Cambia el rol en la base de datos y en la sesión abierta. `rol` es `admin` o `fisio`. |
| `/api/usuarios/activo` | `{id, activo}` | Activa o desactiva. Desactivar cierra la sesión y libera el control. |
| `/api/usuarios/clave` | `{id, clave}` | Cambia la contraseña. No cierra la sesión abierta. |
| `/api/usuarios/borrar` | `{id}` | Borra el perfil, cierra la sesión y libera el control. |

Las rutas de cambio responden `{"ok": true}` o, con `ok: false`:

| Caso | `mensaje` |
|---|---|
| El perfil no existe | `Ese perfil ya no existe.` |
| El perfil es el propio | `Tu propio perfil no se puede cambiar desde aquí.` |
| Rol desconocido | `Ese rol no existe.` |
| Contraseña inválida (además `campo: "clave"`) | El texto de la regla incumplida |

## 4. Reglas del control

El servidor es la autoridad: la página refleja estas reglas, pero una petición que las incumpla se rechaza igual.

1. El control es de una persona, identificada por su `usuario`, no de un dispositivo.
2. Solo puede mover el titular y solo si no hay paro activo (`Camilla.puede_mover`). Cualquier otra orden de movimiento se descarta.
3. El paro de emergencia no depende del control ni de la sesión.
4. Si no hay titular, el primero que toma o solicita el control se lo queda. Al entrar al panel con el control libre, la página llama a `tomar` automáticamente.
5. Si hay titular, quien pide el control queda en solo lectura hasta que el titular acepte.
6. Solo existe un pedido pendiente. El pedido de otra sesión se rechaza mientras haya uno vigente.
7. El titular tiene 30 s para decidir. Al cumplirse, su página responde `aceptar: false`; la página de quien pidió cancela a los 30 s; y el servidor elimina el pedido a los 35 s si nadie lo hizo. El control nunca se transfiere por silencio.
8. Si el titular libera el control o cierra su sesión con un pedido pendiente, el control pasa a quien lo pidió, que recibe `respuesta.aceptada: true`.
9. Cada cambio de titular llama a `parar_motores`.
10. Si el titular pasa 10 s sin ninguna petición, el servidor libera el control aplicando la regla 8.

**Secuencia de cesión del control**

```text
Ana (pide)                       Servidor                     Antonio (titular)
  |--- POST control/solicitar --->|                                  |
  |                               |<------- GET /api/estado ---------|
  |                               |-------- solicitud {id, "Ana"} -->|  Aviso de 30 s
  |                               |<------- POST control/responder --|
  |                               |   Si acepta: cambia el titular   |
  |                               |   y llama a parar_motores        |
  |--- GET /api/estado ---------->|                                  |
  |<-- respuesta, control --------|                                  |
```

## 5. Seguridad del movimiento

| Mecanismo | Dónde actúa | Funcionamiento |
|---|---|---|
| Autorización | Servidor | `puede_mover` se evalúa en cada `mover` y `paso`, y en `detener`. |
| Hombre muerto | Página y servidor | La página repite `/api/mover` cada 400 ms. `vigilar()` detiene el motor si pasa más de 1.0 s sin señal. Como revisa cada 0.5 s, la parada ocurre entre 1.0 y 1.5 s después de la última orden. |
| Soltar el botón | Página | `pointerup`, `pointerleave`, `pointercancel`, pérdida de foco y página oculta llaman a `detenerManual`, que envía `/api/detener`. |
| Cambio de pestaña | Página | Salir de la pestaña Control detiene el movimiento y cancela "Ir a". |
| Cambio de titular | Servidor y página | El servidor llama a `parar_motores`. La página que pierde el control detiene su movimiento. |
| Paro de emergencia | Servidor y página | El servidor llama a `parar_motores` y rechaza `mover` y `paso`. Cada página detiene su movimiento al recibir el estado. |
| Conexión perdida | Página | Tras 3 consultas fallidas seguidas detiene el movimiento y deshabilita los botones. |
| Bloqueo | Página | Deshabilita el movimiento solo en esa pantalla. El paro sigue disponible. |
| Límites de ángulo | Página y servidor | La página usa `CONFIG`. El servidor recorta con `LIMITES`. |

## 6. Posición y telemetría

| En pantalla | Origen | Alcance |
|---|---|---|
| Ángulo de cabeza y de piernas | `telemetria`, que sale de `Camilla.angulos` (valores simulados) | Compartido por todas las pantallas |
| Barra y dibujo de la altura | Variable local `panel.valor.altura` de la página | Solo esa página. Parte de 50 al cargar y no se envía al servidor. |
| "En el tope superior" y "En el tope inferior" | Límites 100 y 0 de la estimación local | Solo esa página |

- `/api/estado` no incluye altura ni finales de carrera. La función `window.camilla.topeAltura()` existe en la página, pero ningún dato del servidor la invoca.
- La altura usa una escala interna de 0 a 100 que nunca se muestra como número. Con el botón pulsado avanza 2 unidades cada 70 ms.
- La página no tiene cifra ni campo "Ir a" para la altura. Cambiar `CONFIG.altura.numerica` a `true` no los agrega: esos elementos no existen en el HTML y el script fallaría.
- Mientras una página mueve la camilla, la cifra se calcula en esa misma página. La telemetría solo se aplica cuando no hay movimiento en curso y pasaron 1.5 s desde la última orden.
- "Ir a" y "Plano 0°" corren en la página: un temporizador de 90 ms envía un `/api/paso` por cada grado y sección.

## 7. Parámetros

**Servidor (`web/servidor.py`)**

| Constante | Valor | Función |
|---|---|---|
| `PUERTO_WEB` | `8000` | Puerto HTTP |
| `IP_RED` | `10.42.0.1` | IP de la Raspberry en la red Camilla. Activa la redirección del portal cautivo. |
| `SIMULACION` | `True` | Ver [Integración con el hardware](#8-integración-con-el-hardware). |
| `TIEMPO_LIBERAR` | `10` s | Tiempo sin contacto del titular antes de liberar el control |
| `ESPERA_SOLICITUD` | `35` s | Duración máxima de un pedido de control en el servidor |
| `HOMBRE_MUERTO` | `1.0` s | Tiempo sin `mover` antes de parar el motor |
| `SESION_HORAS` | `12` h | Tiempo sin uso antes de borrar una sesión |
| `LIMITES` | cabeza `-30` a `70`, piernas `0` a `45` | Límites en grados. Deben coincidir con `CONFIG` de la página. |
| `SECCIONES` | `altura`, `cabeza`, `piernas` | Secciones válidas |

**Base de datos (`web/basedatos.py`)**

| Constante | Valor | Función |
|---|---|---|
| `VUELTAS` | `300_000` | Iteraciones de PBKDF2 |
| `ROLES` | `admin`, `fisio` | Roles válidos |
| `CLAVE_MINIMA` | `6` | Largo mínimo de la contraseña |
| `EDAD_MAXIMA` | `120` | Edad máxima de un paciente |

**Página (`web/publico/js/config.js`)**

```js
export const CONFIG = {
  altura:  { min: 0, max: 100, ref: 0, paso: 2, numerica: false, continua: true,
             etiqueta: 'Altura' },
  cabeza:  { min: -30, max: 70, ref: 0, paso: 1, numerica: true, unidad: '°',
             etiqueta: 'Cabeza' },
  piernas: { min: 0, max: 45, ref: 0, paso: 1, numerica: true, unidad: '°',
             etiqueta: 'Piernas' }
};
```

| Constante | Valor | Función |
|---|---|---|
| `RITMO.esperaRepeticion` | `450` ms | Tiempo pulsado antes de empezar a repetir |
| `RITMO.repeticion` | `160` ms | Intervalo entre pasos de cabeza y piernas al mantener |
| `RITMO.repeticionAltura` | `70` ms | Intervalo de actualización de la altura |
| `RITMO.automatico` | `90` ms | Intervalo entre pasos de "Ir a" y "Plano 0°" |
| `CONSULTA_MS` | `1000` ms | Intervalo de consulta de `/api/estado` |
| `FALLOS_PARA_CAIDA` | `3` | Consultas fallidas seguidas para declarar sin conexión |
| `MANTENER_MS` | `400` ms | Intervalo de repetición de `/api/mover` |
| `ESPERA_SOLICITUD` | `30` s | Espera de quien pide el control |
| `ESPERA_RESPUESTA` | `30` s | Tiempo del titular para decidir |

Tiempos máximos de las peticiones: 2500 ms para `/api/estado`, 8000 ms para `login` y `registro`, 5000 ms para el resto. La página ignora durante 1500 ms el estado del paro tras pulsarlo, para evitar parpadeos.

## 8. Integración con el hardware

No hay hardware conectado. El repositorio no contiene firmware ni código de comunicación con un ESP32; la versión anterior, con ESP32 por USB serial, se retiró en el commit `6249fa0`.

Las órdenes de movimiento terminan en estos métodos de la clase `Camilla`, en el bloque que `web/servidor.py` marca como lugar de las órdenes a los motores. Todos se ejecutan con `candado` tomado.

| Método | Lo llama | Qué hace hoy |
|---|---|---|
| `mover(usuario, seccion, direccion)` | `/api/mover` | Valida, anota el arranque y guarda el motor en `Camilla.motor` |
| `detener(usuario, seccion)` | `/api/detener` | Valida y llama a `parar_motores` si la sección coincide |
| `paso(usuario, seccion, grados)` | `/api/paso` | Valida y actualiza `Camilla.angulos` dentro de `LIMITES` |
| `parar_motores(motivo)` | `detener`, cambio de titular, paro, hombre muerto | Anota la parada y borra `Camilla.motor` |

`SIMULACION` solo cambia la marca "(simulado)" del registro y el campo `simulacion` de `/api/estado`. No activa ni desactiva motores.

Elementos que no existen en esta versión:

- Comunicación con ESP32 o motores.
- Sensores de ángulo y de altura.
- Finales de carrera.
- Corte físico de la alimentación de los motores.

## 9. Base de datos

SQLite, en `web/camilla.db`. `basedatos.iniciar()` crea el archivo con permiso 600 y las tablas si no existen. Cada operación abre su propia conexión, con espera máxima de 5 s si la base está ocupada.

```sql
CREATE TABLE IF NOT EXISTS usuarios (
    id      INTEGER PRIMARY KEY,
    usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nombre  TEXT NOT NULL,
    rol     TEXT NOT NULL DEFAULT 'fisio' CHECK (rol IN ('admin', 'fisio')),
    activo  INTEGER NOT NULL DEFAULT 1,
    sal     TEXT NOT NULL,
    clave   TEXT NOT NULL,
    creado  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pacientes (
    id         INTEGER PRIMARY KEY,
    nombre     TEXT NOT NULL,
    edad       INTEGER NOT NULL,
    creado     TEXT NOT NULL,
    creado_por TEXT NOT NULL
);
```

- `creado` usa el formato `AAAA-MM-DD HH:MM` y la hora del sistema.
- `creado_por` guarda el usuario como texto, sin relación con la tabla `usuarios`.

**Contraseñas.** `clave` guarda en hexadecimal el resultado de PBKDF2-HMAC-SHA256 con 300 000 iteraciones. `sal` son 16 bytes aleatorios por perfil. La comparación usa `hmac.compare_digest`. Si el usuario no existe se hace el mismo cálculo, para que el tiempo de respuesta no revele si existe.

### Validación

Las reglas de perfiles están en `web/basedatos.py` y repetidas en `web/publico/js/ui/formularios.js` y `web/publico/js/vistas/acceso.js`. El servidor siempre las aplica.

| Campo | Regla | Patrón o límite |
|---|---|---|
| `nombre` del perfil | 2 a 40 letras sin tildes | `[A-Za-z]{2,40}` |
| `usuario` | 3 a 20 letras o números, guardado en minúsculas | `[a-z0-9]{3,20}` |
| `clave` | 6 a 100 letras o números | `[A-Za-z0-9]*`, largo de 6 a 100 |
| `nombre` del paciente | Mínimo 2 caracteres, cortado a 80 | Texto libre |
| `edad` | Entero de 0 a 120 | No acepta texto ni booleanos |

### Comandos de terminal

| Comando | Efecto |
|---|---|
| `python3 web/basedatos.py` | Lista los perfiles y avisa si no hay administrador |
| `python3 web/basedatos.py admin USUARIO` | Asigna el rol de administrador y activa el perfil |
| `python3 web/basedatos.py clave USUARIO` | Pide y guarda una contraseña nueva |
| `python3 web/basedatos.py revisar` | Solo avisa si no hay administrador. Lo usa `encender_red.sh`. |

## 10. Estructura del panel web

### 10.1 Organización

El panel es una sola página, organizada en tres partes sin paso de compilación. La Raspberry solo necesita Python; el navegador carga los módulos JavaScript directamente.

| Carpeta | Contenido |
|---|---|
| `web/plantillas/` | HTML en parciales. `index.html` es el esqueleto. Cada `<!-- incluir: ruta -->` se reemplaza por ese archivo, con la ruta relativa a `plantillas/`. |
| `web/publico/css/` | Estilos propios. Se cargan después de Bootstrap, en el orden de `index.html`. |
| `web/publico/js/` | Módulos JavaScript. `main.js` es el punto de entrada. |

Las dependencias entre módulos no forman ciclos. Cada módulo con eventos expone una función `iniciar...` y `main.js` las llama en orden. Los datos de entrada llegan únicamente por `api/sondeo.js`, que recibe sus funciones de `main.js`.

Los atributos `id` del HTML enlazan las plantillas con JavaScript. Al renombrar o quitar uno hay que actualizar el módulo que lo usa; si falta, el panel falla con un error de JavaScript.

### 10.2 Servidor y red

| Archivo | Qué es y para qué sirve | Qué se modifica aquí |
|---|---|---|
| `web/servidor.py` | Servidor HTTP. Atiende la API, guarda el estado compartido en la clase `Camilla`, aplica las reglas del control y ejecuta la vigilancia periódica. | Constantes del inicio (`PUERTO_WEB`, `IP_RED`, `TIEMPO_LIBERAR`, `ESPERA_SOLICITUD`, `HOMBRE_MUERTO`, `SESION_HORAS`, `LIMITES`). Reglas del control y órdenes a los motores en `Camilla`. Rutas en `ACCIONES`, `administrar` y `do_POST`. `encender_red.sh` lee las frases de `anotar()`: al cambiarlas hay que ajustar su monitor. |
| `web/paginas.py` | Compone el HTML desde `plantillas/` y entrega los archivos de `publico/`. | Tipos de archivo que se entregan (`TIPOS`) y la forma de resolver los `incluir` (`INCLUIR`, `componer`). |
| `web/basedatos.py` | Acceso a SQLite: perfiles, contraseñas, pacientes y comandos de terminal. | Tablas (`TABLAS`), roles (`ROLES`), reglas de perfiles (`revisar_clave`, `crear_usuario`) y de pacientes (`guardar_paciente`), `CLAVE_MINIMA`, `EDAD_MAXIMA`, `VUELTAS` y los comandos de terminal. |
| `web/camilla.db` | Base de datos SQLite. La crea `basedatos.py` y no se sube a git. | No se edita a mano. Se administra desde el panel o con `web/basedatos.py`. |
| `red/instalar_red.sh` | Instala `hostapd` y crea la configuración de la red WiFi. Se ejecuta una vez. | Nombre y parámetros de la red: `ssid`, `country_code`, `hw_mode`, `channel`. |
| `red/encender_red.sh` | Enciende y apaga la red y la página, y muestra los eventos en vivo. | Dirección IP y rango de DHCP (`--dhcp-range`), redirección de puertos y mensajes del monitor (bloque `case`). |

### 10.3 Plantillas HTML

Las rutas son relativas a `web/plantillas/`.

| Archivo | Qué es y para qué sirve | Qué se modifica aquí |
|---|---|---|
| `index.html` | Esqueleto de la página: cabecera, carga de estilos y scripts, e inclusión de las partes principales. | Título, hojas de estilo y su orden, inclusión de modales y zona de toasts (`zonaToasts`). |
| `login.html` | Vista `vistaLogin`: inicio de sesión (`formLogin`) y creación de perfil (`formRegistro`). | Campos, rótulos y textos de ayuda de la pantalla de acceso. |
| `paro-flotante.html` | Botón de paro visible en el acceso, sobre los modales y en las pestañas de administración. | Contenido e icono de ese botón. |
| `panel/panel.html` | Vista `vistaPanel`: reúne encabezado, barra de pestañas y contenido de cada pestaña. | Bloques que forman el panel e inclusión de pestañas. |
| `panel/encabezado.html` | Título, perfil de la persona y botones Bloquear y Salir. | Nombre del equipo, datos del perfil y botones del encabezado. |
| `panel/pestanas.html` | Barra de pestañas del administrador. | Botones de pestaña (`data-pestana`), textos e iconos. |
| `panel/registros.html` | Pestaña Registros: formulario y tabla de pacientes. | Campos del formulario, columnas y buscador. |
| `panel/usuarios.html` | Pestaña Usuarios: tabla de perfiles. | Columnas y texto de ayuda. |
| `panel/control/control.html` | Pestaña Control: acomoda sus bloques. | Orden y columnas de los bloques de control. |
| `panel/control/barra-control.html` | Barra que muestra quién tiene el control. | Estructura de la barra. Los textos y botones cambian en `ui/pintado.js`. |
| `panel/control/cinta-paro.html` | Aviso de paro de emergencia activo. | Texto e icono del aviso. |
| `panel/control/diagrama.html` | Dibujo SVG de la camilla y su leyenda. | Formas del dibujo y leyenda. Las coordenadas deben coincidir con `ui/dibujo.js`. |
| `panel/control/altura.html` | Tarjeta de altura: botones Subir y Bajar, y riel. | Textos y botones. Cada botón indica `data-seccion` y `data-dir`. |
| `panel/control/cabeza.html` | Tarjeta de cabeza: lectura, riel, botones y campo "Ir a". | Textos, botones y campo de esa sección. |
| `panel/control/piernas.html` | Tarjeta de piernas: lectura, riel, botones y campo "Ir a". | Textos, botones y campo de esa sección. |
| `panel/control/barra-seguridad.html` | Barra inferior: luz de estado, Plano 0° y Paro. | Botones y distribución de la barra. |
| `panel/control/registro-comandos.html` | Desplegable "Registro de comandos (desarrollo)". | Título y presentación del desplegable. |
| `modales/tomar.html` | `modalTomar`: ofrece tomar el control. | Título, texto y botones de ese aviso. |
| `modales/solicitar.html` | `modalSolicitar`: ofrece pedir el control. | Título, texto y botones de ese aviso. |
| `modales/esperando.html` | `modalEsperando`: espera la respuesta del titular. | Título, texto y barra de cuenta regresiva. |
| `modales/entrante.html` | `modalEntrante`: el titular decide un pedido. | Título, texto, botones y barra de cuenta regresiva. |
| `modales/sin-conexion.html` | `modalSinConexion`: se perdió la conexión. | Título, texto y botón Reintentar. |
| `modales/confirmar.html` | `modalConfirmar`: confirmación genérica. | Estructura. Cada texto lo define quien llama a `confirmar`. |
| `modales/clave.html` | `modalClave`: contraseña nueva para otro perfil. | Campo y textos del formulario. |

### 10.4 Hojas de estilo

Las rutas son relativas a `web/publico/css/`.

| Archivo | Qué es y para qué sirve | Qué se modifica aquí |
|---|---|---|
| `tokens.css` | Paleta del proyecto y variables de Bootstrap. | Colores de cada sección (`--cabeza`, `--piernas`, `--altura`), colores generales, fuentes y contraste. |
| `base.css` | Estructura general de la página y piezas compartidas. | Márgenes y ancho máximo, tipografía (`.tipo-titulo`, `.tipo-dato`), rótulos de campo, marcos de icono y reducción de movimiento. |
| `botones.css` | Apariencia de los botones propios. | Botones de movimiento (`.btn-mover`), "Ir" (`.btn-ir`), botones grandes (`.btn-accion` y variantes), de formulario (`.btn-formulario`) y de barra (`.btn-barra`). |
| `secciones.css` | Tarjetas de altura, cabeza y piernas. | Color de acento por sección, número grande (`.cifra`), campo de ángulo y riel de recorrido (`.riel-*`). |
| `camilla.css` | Apariencia del dibujo SVG. | Colores, trazos, animaciones del dibujo y leyenda (`.punto`). |
| `panel.css` | Partes fijas del panel. | Encabezado, barra de control (`.control-barra`), luz de estado (`.estado`), barra inferior, paro flotante y registro de comandos. |
| `modales.css` | Modales y avisos. | Franja superior (`.modal-tope`, `.tope-*`), tonos de icono, cuenta regresiva y colores de los toasts (`.aviso-*`). |
| `login.css` | Pantalla de acceso. | Tamaño y posición de la caja y sus títulos. |
| `admin.css` | Pestañas y tablas del administrador. | Pestañas (`.pestanas`), tablas (`.tabla-admin`), buscador y tarjeta de paciente. |

### 10.5 Módulos JavaScript

Las rutas son relativas a `web/publico/js/`.

| Archivo | Qué es y para qué sirve | Qué se modifica aquí |
|---|---|---|
| `main.js` | Punto de entrada: conecta los módulos y arranca el panel. | Orden de arranque y llamadas `iniciar...` de módulos nuevos. |
| `config.js` | Parámetros del panel. | `CONFIG` (recorridos y pasos), `RITMO`, `SECCIONES`, `SUFIJO`, `ROLES` y tiempos de consulta y espera. |
| `estado.js` | Estado compartido: `panel`, `control`, `sesion`. | Datos nuevos compartidos entre módulos y la regla `puedeMover`. |
| `utilidades.js` | Funciones generales: `porId`, `signo`, `conSigno`, `esc`, `sinTildes`. | Funciones que no dependen de ninguna parte del panel. |
| `recepcion.js` | Aplica lo que informa el servidor: `recibir`, `reconectado`, `caidaDeConexion`. | Qué hace el panel con cada campo de `/api/estado` y con la pérdida de conexión. `ECO_MS`. |
| `api/cliente.js` | Peticiones HTTP y token de sesión: `pedir`, `llamar`, `enviar`, `guardarToken`. | Cabeceras, plazo por defecto y almacenamiento del token. |
| `api/sondeo.js` | Consulta periódica de `/api/estado`: `consultar`, `iniciarSondeo`. | Forma de obtener el estado y su plazo (`PLAZO_MS`). |
| `api/ordenes.js` | Objeto `SERVIDOR`: órdenes de sesión, movimiento, paro y control. | Rutas y datos de esas órdenes, y órdenes nuevas. |
| `api/admin.js` | Objeto `ADMIN`: pedidos de pacientes y perfiles. | Rutas y datos de administración. |
| `camilla/movimiento.js` | Lógica del movimiento y del paro: `iniciarManual`, `detenerManual`, `irA`, `activarParo`, `liberarParo`, `alternarParo`. | Cómo avanza cada paso, la repetición al mantener, "Ir a", el paro y `DURACION_TOPE_MS`. |
| `camilla/mandos.js` | Conecta los controles con el movimiento. | Eventos de los botones, teclas (`TECLAS_PULSAR`, Esc), campo "Ir a" y botones Plano, Paro y Bloquear. |
| `camilla/telemetria.js` | Lecturas de la camilla y objeto público `window.camilla`. | Cómo se aplican las lecturas (`aplicarAngulos`) y los miembros de `window.camilla`. |
| `ui/pintado.js` | Lleva el estado a la pantalla: `pintar`. | Rieles, textos de estado, botones habilitados, barra de control (`datosBarraControl`), paro flotante y anuncio de voz. |
| `ui/dibujo.js` | Anima el dibujo de la camilla. | Geometría (`PIVOTE`, `R_ARCO`, `AMPLITUD_PX`, `SUPERFICIE_Y`, `PISTON_BASE`) y su animación. |
| `ui/modales.js` | Gestión de modales: `abrirModal`, `cerrarModal`, `confirmar`, `iniciarCuenta`. | Comportamiento común de los modales, cuenta regresiva y confirmación. |
| `ui/avisos.js` | Toasts (`mostrarAviso`) y revisión de respuestas (`revisar`). | Duración (`DURACION_MS`), tipos de aviso y mensaje de error de conexión. |
| `ui/formularios.js` | Reglas y ayudas de los formularios: `revisarClave`, `marcarCampo`, `ocupado`. | Reglas de caracteres y contraseña, y sus mensajes. Deben coincidir con `web/basedatos.py`. |
| `ui/registro.js` | Registro de comandos: `registrar`, `iniciarDiagnostico`. | Cantidad de líneas (`MAXIMO_LINEAS`, `LINEAS_VISIBLES`) y captura de errores. |
| `vistas/acceso.js` | Formularios de inicio de sesión y creación de perfil. | Validación y mensajes de esos formularios, y `PAUSA_BIENVENIDA_MS`. |
| `vistas/sesion.js` | Entrada y salida del panel: `entrarAlPanel`, `sesionTerminada`. | Qué ocurre al entrar o salir, incluida la toma automática del control. |
| `vistas/cesion.js` | Titular del control y pedidos: `aplicarControl`, `pedirControl`, `atenderSolicitud`, `resolverSolicitud`. | Flujo y avisos al tomar, pedir, ceder o liberar el control. |
| `vistas/pestanas.js` | Pestañas del panel y permisos por rol: `aplicarRol`. | Lista `PESTANAS`, qué se carga al abrir cada una y qué ve cada rol. |
| `vistas/pacientes.js` | Pestaña Registros. | Filas de la tabla (`filaPaciente`), búsqueda, validación, guardado y borrado. |
| `vistas/usuarios.js` | Pestaña Usuarios. | Filas de la tabla (`filaUsuario`), opciones del menú (`menuAcciones`, `ACCIONES`) y sus confirmaciones. |

### 10.6 Bootstrap y fuentes

Las rutas son relativas a `web/publico/vendor/`. Son archivos de terceros: no se editan, solo se reemplazan por otra versión completa. Los ajustes visuales van en `web/publico/css/`.

| Archivo | Qué es y para qué sirve | Qué se modifica aquí |
|---|---|---|
| `bootstrap.min.css` | Estilos de Bootstrap 5.3.3. | Se reemplaza al actualizar Bootstrap. |
| `bootstrap.bundle.min.js` | JavaScript de Bootstrap 5.3.3: modales, toasts y menús. | Se reemplaza al actualizar Bootstrap, junto con el CSS. |
| `fuentes.css` | Declara las fuentes guardadas en `fuentes/`. | Fuentes y pesos disponibles. |
| `fuentes/*.woff2` | Barlow Condensed, IBM Plex Mono e IBM Plex Sans. | Se agregan o reemplazan archivos de fuente. |
| `fuentes/LICENCIA.txt` | Licencia de las fuentes. No se entrega por HTTP. | Se actualiza si cambian las fuentes. |

### 10.7 Cambios que abarcan varios archivos

| Cambio | Archivos |
|---|---|
| Límite de ángulo | `LIMITES` en `web/servidor.py` y `CONFIG` en `publico/js/config.js` |
| Puerto o dirección IP | `PUERTO_WEB` e `IP_RED` en `web/servidor.py`, y `red/encender_red.sh` |
| Reglas de perfiles | `web/basedatos.py`, `ui/formularios.js` y `vistas/acceso.js` |
| Campo nuevo de paciente | `TABLAS` y `guardar_paciente` en `web/basedatos.py`, `panel/registros.html` y `vistas/pacientes.js`. Una base ya creada no recibe la columna nueva. |
| Hoja de estilo nueva | El archivo en `publico/css/` y su `<link>` en `plantillas/index.html` |
| Módulo JavaScript nuevo | El archivo en `publico/js/`, su `import` en el módulo que lo usa y, si tiene eventos, su `iniciar...` en `main.js` |
| Modal nuevo | Su archivo en `plantillas/modales/`, su `incluir` en `plantillas/index.html` y la llamada a `abrirModal` en el módulo que lo abre. `ui/modales.js` lo registra solo. |
| Pestaña nueva | Su parcial en `plantillas/panel/`, su `incluir` en `panel/panel.html`, su botón en `panel/pestanas.html`, su entrada en `PESTANAS` de `vistas/pestanas.js`, y su módulo en `vistas/` con su `iniciar...` en `main.js` |

### 10.8 Vistas, modales y API pública

**Vistas**

| Elemento | Contenido |
|---|---|
| `vistaLogin` | Inicio de sesión y creación de perfil |
| `vistaPanel` | Panel, con las pestañas `pestanaControl`, `pestanaRegistros` y `pestanaUsuarios`. Las dos últimas y la barra de pestañas solo aparecen con rol `admin`. |

**Avisos modales.** Usan el componente de Bootstrap con fondo estático y sin cierre por tecla Esc. Cada uno está en su archivo de `web/plantillas/modales/`, y `ui/modales.js` registra todo elemento `.modal` de la página.

| Identificador | Cuándo aparece |
|---|---|
| `modalTomar` | Nadie opera la camilla y se pulsa "Tomar el control" |
| `modalSolicitar` | Otra persona tiene el control y se ofrece pedirlo |
| `modalEsperando` | Se espera la respuesta del titular, con cuenta de 30 s |
| `modalEntrante` | El titular decide un pedido, con cuenta de 30 s |
| `modalSinConexion` | La conexión con el servidor se perdió |
| `modalConfirmar` | Confirmación de acciones de administración |
| `modalClave` | Contraseña nueva para otro perfil |

**Objeto `window.camilla`**

| Miembro | Función |
|---|---|
| `aplicarAngulos({cabeza, piernas})` | Aplica una lectura de ángulos a la pantalla |
| `topeAltura('superior' o 'inferior' o null)` | Marca un final de carrera de altura en la pantalla |
| `estado()` | Devuelve `{cabeza, piernas, paro, bloqueo}` |
| `irA(objetivos, nombre)` | Inicia un movimiento a un destino |
| `paro(remoto)` | Activa el paro |

**Registro de comandos.** El desplegable "Registro de comandos (desarrollo)", al final de la pestaña Control, muestra las últimas órdenes, respuestas y errores de JavaScript de esa página.

## 11. Comportamientos a tener en cuenta

Comportamientos de la versión actual, comprobados contra el código.

**Paro de emergencia**

- El botón de paro alterna entre activar y liberar sin confirmación: un segundo toque libera el paro. Ocurre también con el botón flotante de la pantalla de inicio de sesión.
- Liberar no requiere sesión, y una petición sin el campo `activo` libera el paro.
- El estado está en memoria: al reiniciar el servidor el paro queda inactivo.
- Es un estado lógico del servidor y no corta físicamente la alimentación.

**Movimiento**

- Cada petición usa su propia conexión, sin orden garantizado entre ellas. Si un `/api/mover` repetido llega después de `/api/detener`, el motor vuelve a quedar en marcha hasta que actúa el hombre muerto.
- `Camilla.motor` guarda un solo motor continuo a la vez.
- "Ir a" y "Plano 0°" dependen de la página: si se cierra, el movimiento queda a medias.
- La altura estimada llega de media carrera a un límite en 1.75 s de botón pulsado. Al llegar, la página envía `/api/detener` y deshabilita el botón.

**Acceso**

- Cualquier persona con acceso a la red puede crear un perfil de fisioterapeuta.
- `/api/estado` sin sesión muestra el titular, el paro y los ángulos.
- No hay límite de intentos por dirección IP. Cada intento fallido tarda 1 s adicional.
- Cambiar la contraseña de un perfil no cierra su sesión abierta.

**Mantenimiento**

- Los límites de ángulo están duplicados en `LIMITES` y `CONFIG`.
- `CREATE TABLE IF NOT EXISTS` no modifica tablas existentes: una columna nueva no se agrega a una base ya creada.
