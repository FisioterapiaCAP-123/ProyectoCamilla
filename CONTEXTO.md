# Contexto del proyecto

**Actualizado el 20-11-2026.** Rama `desarrollo-final`, creada ese día desde `master` (`1eaf7a2`, del 16-11) para terminar el desarrollo. El software se revisó contra el código de esta rama, archivo por archivo. Lo que no se puede comprobar desde el PC (hardware, Raspberry) viene de las notas anteriores, con la fecha en que se probó, o se marca "sin confirmar".

- La versión anterior de este archivo, con la historia del 09-11 al 16-11, el análisis completo de sensores de ángulo y el diseño del encoder, se ve con `git show 1eaf7a2:CONTEXTO.md`.
- **Otras ramas: no se usan como referencia**, salvo que el usuario lo pida. `manuales` (manuales de la tesis y un diseño con AS5600 sin montar), `muestra-citein` (interfaz sin grados de la presentación del 13-11), `backup-cambios-esp32` (encoder; tiene `codigoesp32.txt` con la clave del WiFi), `esp32-conexion` y `optimizaciones-esp32` (viejas).
- `GUIA.md` e `INTEGRACION.md` están desactualizadas: describen el sistema en simulación, sin ESP32 (ver la sección 9).

## 1. Estado en una mirada

| Parte | Estado |
|---|---|
| Control desde el celular | Funciona. El 13-11 las tres secciones se movieron desde la página con la placa real. |
| Piernas | 2 actuadores 1500N en paralelo en un BTS7960 (GPIO 26 y 27). Probado en la placa real el 11-11. |
| Cabeza | 1 actuador 3000N (de 2) en un L298N (GPIO 18 y 19). Probado en la placa real. Faltan su BTS7960 y el segundo actuador. |
| Altura | NEMA 17 con DRV8825 (GPIO 25, 33 y 13). Probado sin carga el 13-11. Sin finales de carrera en `main.py`. Husillo sin definir. |
| Ángulos y altura en pantalla | Estimados: no hay sensores. Cada página calcula su propia estimación y las demás pantallas no la ven. |
| "Ir a" y "Plano 0°" | Solo mueven el número y el dibujo. No mueven motores. |
| Seguridad del movimiento | Hombre muerto en la página, el servidor y el ESP32; watchdog; órdenes numeradas; paro lógico. **No hay paro físico.** |
| Perfiles, roles y pacientes | Completo, en SQLite. Registro de perfiles abierto. Sin bitácora de uso. |
| Red Camilla y arranque automático | Instalados y funcionando en la Raspberry desde el 12-11. |
| Tiempo real | Sin WebSocket: la página consulta cada 1 s. |

## 2. Arquitectura

```text
Navegador (celular o PC)
  GET  /api/estado cada 1 s
  POST /api/mover cada 400 ms mientras se mantiene un botón; /api/detener al soltar
      |  WiFi "Camilla" (hostapd, WPA2, sin internet). La Raspberry es 10.42.0.1
Raspberry Pi 4: web/servidor.py en el puerto 8000 (ThreadingHTTPServer, HTTP/1.0)
  Camilla (en memoria, con candado): sesiones, titular, pedido de control, paro, motor
  vigilar() cada 0.5 s: hombre muerto, ESP32 perdido, titular caído, pedidos vencidos
  basedatos.py -> web/camilla.db
  hardware.py: Esp32Serial (hilo propio, una línea cada 200 ms) o Simulador (--simulador)
      |  USB serie a 115200 (CP2102, /dev/ttyUSB0)
ESP32 WROOM-32 con esp32/main.py (MicroPython v1.29.0)
  piernas -> BTS7960 (26, 27) -> 2 actuadores 1500N
  cabeza  -> L298N (18, 19)   -> 1 actuador 3000N
  altura  -> DRV8825 (25 STEP, 33 DIR, 13 EN) -> NEMA 17
```

**Una orden de punta a punta** (mantener "Subir" de Cabeza):

1. `pointerdown` → `iniciarManual('cabeza', 1)` en `camilla/movimiento.js`. Primero llama a `detenerTodo()`; después `SERVIDOR.mover` manda `POST /api/mover {seccion, dir, n}` y lo repite cada 400 ms. Cada 70 ms suma 1° a la estimación local.
2. `servidor.py`: `accion_mover` descarta la orden si su `n` es viejo. `Camilla.mover` exige ser el titular, que no haya paro y que el ESP32 esté vivo e informe esa sección; si no, la descarta en silencio. Guarda `Camilla.motor` y llama a `hardware.mover`.
3. `hardware.py` guarda la orden (una sola a la vez). Su hilo escribe `M cabeza 1*XX` al momento y después cada 200 ms.
4. ESP32: arranca la sección si pasaron los 300 ms de pausa y responde a cada orden válida con `E altura=detenido cabeza=extendiendo piernas=detenido*XX`.
5. Al soltar: `POST /api/detener` → `parar_motores` → el hilo manda `X`, que detiene todas las secciones.

**Si algo se corta:**

| Falla | Quién para | En cuánto |
|---|---|---|
| Se suelta el botón o la página se oculta | Página → servidor → `X` | Lo que tarde la red |
| El celular pierde el WiFi | Servidor (`HOMBRE_MUERTO`) | Entre 1.0 y 1.5 s |
| Se cuelga o cae el servidor, o se corta el USB | ESP32 (`LIMITE_SIN_ORDEN_MS`) | 0.5 s |
| Se cuelga `main.py` | Watchdog del ESP32: reinicia la placa con todo apagado | 2 s |
| Paro en cualquier pantalla | Servidor → `X` | Lo que tarde la red |

**Estructura:**

```text
esp32/        main.py (firmware), prueba_stepper.py (prueba del stepper en Thonny)
red/          instalar_red.sh, encender_red.sh, instalar_arranque.sh, arranque_red.sh
web/          servidor.py, hardware.py, basedatos.py, paginas.py, datos_prueba.py
  plantillas/ index.html y parciales: login.html, paro-flotante.html, panel/ (control/, registros, usuarios), modales/
  publico/    lo único que se entrega por HTTP: css/, js/ (api/, camilla/, ui/, vistas/), vendor/ (Bootstrap y fuentes)
CONTEXTO.md, GUIA.md, INTEGRACION.md, README.md
compi.txt     (sin seguimiento en git) código del compañero. TIENE LA CLAVE DEL WIFI: no se sube.
```

## 3. ESP32: `esp32/main.py`

**Placa:** ESP32 WROOM-32 con CP2102 (`10c4:ea60`), MicroPython v1.29.0. En la placa hay un `boot.py` sin lógica y nuestro `main.py`. Al abrir el puerto la placa se reinicia (`rst:0x1`) y en 1 a 2 s imprime `# camilla lista`.

**Configuración** (al inicio del archivo; se cambia antes de cargarlo):

| Constante | Valor | Para qué |
|---|---|---|
| `MODULO` | `"puente"` | `"puente"`: piernas, cabeza y altura. `"reles"`: solo cabeza con el módulo de 4 relés (no crea la altura). |
| `PIN_EXTENDER`, `PIN_RETRAER` | 26, 27 | Piernas: RPWM y LPWM del BTS7960 |
| `PIN_HABILITAR` | `None` | R_EN y L_EN van a 3.3 V. Con un GPIO, se apaga al parar. |
| `CABEZA_EXTENDER`, `CABEZA_RETRAER` | 18, 19 | Cabeza: IN1 e IN2 del L298N (ENA con su jumper) |
| `VELOCIDAD`, `FRECUENCIA_PWM` | 100 %, 1000 Hz | Puentes H: siempre a toda potencia |
| `ALTURA_STEPPER` | `True` | Crea la sección `altura` |
| `ALTURA_STEP`, `ALTURA_DIR`, `ALTURA_EN` | 25, 33, 13 | DRV8825: STP, DIR y EN (EN activo en bajo) |
| `SUBIR_CON_DIR` | 1 | Si "Subir" baja, se pone 0 |
| `PASOS_INICIO`, `PASOS_ACELERACION`, `PASOS_VELOCIDAD` | 250, 1500, 1000 | Arranca a 250 pasos/s y llega a 1000 en 0.5 s (5 vueltas/s en paso completo). A 1000 de golpe un NEMA 17 zumba y no arranca. Si zumba o se atora con carga: 800 o 600. |
| `MANTENER_FUERZA` | `True` | Quieto, el stepper sigue sujetando (EN siempre en 0) y se calienta |
| `ACTIVO_BAJO` | `True` | Solo para los relés |
| `PAUSA_CAMBIO_MS` | 300 | Pausa entre apagar una sección y volver a arrancarla o invertirla |
| `LIMITE_SIN_ORDEN_MS` | 500 | Sin `M` en ese tiempo, la sección para sola |
| `WATCHDOG_MS` | 2000 | Watchdog, activado con la primera línea válida (así Thonny puede entrar antes) |
| `LARGO_MAXIMO` | 64 | Una línea más larga se descarta |

**Clases:**

- `PuenteH(pin_a, pin_b, pin_habilitar=None)`: un canal de L298N o un BTS7960. `"a"` extiende y `"b"` retrae; nunca los dos a la vez. Las salidas se crean en 0 (`salida_pwm`), porque algunas versiones arrancan el PWM a medias.
- `Stepper(step, dir, en)`: el PWM en STEP da un pulso por paso y su frecuencia es la velocidad. `"a"` sube. `actualizar()` hace la rampa y solo cambia la frecuencia cada 10 pasos/s. `poner_velocidad` suma 1 si la frecuencia sería 1000 Hz, para no compartir reloj con los puentes H.
- `ParReles(pin_a, pin_b)`: dos relés por actuador, del código del compañero. Solo con `MODULO = "reles"` (26/27 y 25/33).
- `Seccion(pares)`: los actuadores de una sección arrancan, paran e invierten juntos. Lleva `marcha` (lo que está encendido), `pedido` (lo que pide la Raspberry), `visto` (último `M`) y `libre_desde` (fin de la pausa).

**Secciones creadas hoy:** `piernas` = `PuenteH(26, 27)`, `cabeza` = `PuenteH(18, 19)` y `altura` = `Stepper(25, 33, 13)`. Si el stepper falla al crearse, imprime `# altura desactivada: ...` y las otras dos siguen. Para agregar una sección se edita `SECCIONES`: el servidor la detecta sola por las líneas `E`.

**Protocolo por USB.** Una orden por línea, terminada en `*XX` (XOR de los caracteres, en hexadecimal):

```text
Raspberry -> ESP32   M <seccion> 1    extender o subir; se repite cada 200 ms
                     M <seccion> -1   retraer o bajar
                     S <seccion>      detener esa sección (el servidor no la usa)
                     X                detener todo
                     P                sigo aquí (cuando no hay movimiento)
ESP32 -> Raspberry   E altura=detenido cabeza=extendiendo piernas=contrayendo*XX
                     # camilla lista | # altura desactivada: ... | # error: ...
```

- Responde `E` a toda línea con comprobación correcta, aunque la orden no sea válida. Las líneas con comprobación mala se ignoran (si era un `M`, la sección para sola a los 500 ms).
- El LED azul (GPIO 2) está encendido mientras alguna sección está en marcha.
- Ctrl+C (Thonny) detiene todo y, si el watchdog ya estaba activo, reinicia la placa para que Thonny pueda entrar. Cualquier otro error detiene todo, imprime `# error: ...` y reinicia.

**No hace:** leer finales de carrera, contar pasos de la altura, medir corriente, limitar el tiempo de marcha ni informar posición. Los estados de la línea `E` llegan al servidor, pero el servidor solo usa los nombres de las secciones.

**`esp32/prueba_stepper.py`:** prueba del motor de la altura desde la consola de Thonny (F5; no se guarda como `main.py`). Órdenes `s`, `b`, `s 400`, `b 400`, `p`, `v 600`, `0` y `?`. Genera los pulsos a mano (no con PWM), con rampa y frenado, a 400 pasos/s por omisión, y para solo a los 15 s. Ya lee los finales de carrera con `USAR_FINALES = True`: normalmente abiertos a GND, GPIO 4 (abajo, con la resistencia interna) y GPIO 35 (arriba, con 10 kΩ a 3.3 V porque no tiene interna). Su docstring tiene la conexión completa del DRV8825.

## 4. Servidor

### `web/hardware.py`

- `Simulador`: no mueve nada y dice que las tres secciones existen. Se usa con `python web/servidor.py --simulador`.
- `Esp32Serial`: un hilo propio abre el puerto, escribe y lee. `mover()` y `parar()` solo dejan la orden lista y despiertan al hilo: nunca esperan al puerto, porque se llaman con `candado` tomado.
  - Busca el puerto por el fabricante del chip USB (CP210x `0x10C4`, CH340 `0x1A86`, FTDI `0x0403`) o usa la variable `CAMILLA_PUERTO`.
  - Abre a 115200 con `exclusive=True` (si Thonny tiene el puerto, no lo comparte) y DTR/RTS en bajo (en alto la placa se queda reiniciando).
  - Guarda **una sola orden** `(seccion, direccion)`. Cada 200 ms (`CADA_ORDEN`) manda `M` con esa orden, o `P` si no hay. `parar()` deja un `X` pendiente, que sale primero.
  - El ESP32 cuenta como vivo si hubo una línea `E` válida hace menos de 1 s (`SILENCIO_MAXIMO`). `disponible(seccion)` exige que esté vivo y que haya informado esa sección.
  - Si pasan 3 s sin respuesta (`SILENCIO_REABRIR`), cierra y reabre el puerto. Al abrir espera hasta 6 s (`ESPERA_ARRANQUE`), porque la placa se reinicia. Reintenta cada 2 s.
  - `avisar()` anota cada mensaje una sola vez seguida: `ESP32 conectado en ...: altura, cabeza, piernas`, `el ESP32 dejo de responder`, `se perdio la conexion con el ESP32: dejo de responder`, `... no respondio al abrir el puerto (revisa que tenga cargado esp32/main.py)`, `no se encontro el ESP32 en ningun puerto USB` y `falta pyserial: sudo apt install python3-serial`.

### `web/servidor.py`

| Constante | Valor | Para qué |
|---|---|---|
| `PUERTO_WEB` | 8000 | Puerto HTTP, en todas las interfaces (`0.0.0.0`) |
| `IP_RED` | `10.42.0.1` | IP en la red Camilla; activa la redirección del portal |
| `TIEMPO_LIBERAR` | 10 s | Sin noticias del titular, el control se libera |
| `ESPERA_SOLICITUD` | 35 s | Vida de un pedido de control (la página cuenta 30) |
| `HOMBRE_MUERTO` | 1.0 s | Sin `/api/mover`, se para el motor |
| `SESION_HORAS` | 12 h | Una sesión sin uso se borra |
| `LIMITES` | cabeza −30 a 70, piernas 0 a 45 | Solo los usa `/api/paso` |

**Estado (`Camilla`, en memoria):** `sesiones` (token → perfil), `titular`, `solicitud`, `respuestas`, `paro`, `angulos` (siempre 0: nadie usa `/api/paso`), `motor` (una sección a la vez) y `hardware`. Reiniciar el servidor borra todo esto: saca a todos y libera el paro.

**Reglas:**

- **Sesión:** un perfil, una sesión. Entrar desde otro dispositivo cierra la anterior, y el control no pasa al nuevo.
- **Control:** un solo titular. Libre: lo toma quien entra (la página lo pide sola). Ocupado: solo lectura, y se puede pedir. El titular acepta o rechaza; si libera con un pedido pendiente, el control pasa a quien lo pidió. Cambiar de titular para el motor.
- **Paro:** cualquiera lo activa o lo libera, incluso sin sesión. Activarlo para el motor y bloquea `mover` y `paso`.
- **`vigilar()`** cada 0.5 s: hombre muerto, ESP32 perdido con motor en marcha, titular sin contacto 10 s, pedido vencido a los 35 s y sesiones de más de 12 h.

**Rutas:**

| Ruta | Sesión | Qué hace |
|---|---|---|
| `GET /api/estado` | Opcional (`X-Sesion`) | `usuario`, `nombre`, `rol`, `control {titular, usuario}`, `paro`, `simulacion`, `hardware {conectado, secciones}`, `solicitud` (solo al titular), `respuesta` (solo a quien pidió, una vez) y `telemetria {cabeza, piernas}` (siempre 0) |
| `GET /` y archivos | No | La página compuesta; de `publico/` solo `.css`, `.js` y `.woff2` |
| `POST /api/login`, `/api/registro` | No | Abre una sesión. El registro crea un fisioterapeuta. `recordar: true` en el login devuelve además una `llave` para el equipo. Un login sin `recordar` anula las llaves de otros equipos del perfil. |
| `POST /api/reanudar {llave}` | No | Equipo recordado: abre sesión sin contraseña. Vale 30 días desde el último uso. La anulan entrar desde otro equipo, "Salir", una contraseña nueva, desactivar o borrar el perfil. |
| `POST /api/paro {activo}` | No | `activo: true` lo activa; cualquier otra cosa lo libera, también `{}` |
| `POST /api/logout` | Sí | Cierra la sesión y libera el control si lo tenía |
| `POST /api/control/tomar`, `solicitar`, `cancelar`, `responder {id, aceptar}`, `liberar` | Sí | Control |
| `POST /api/mover {seccion, dir, n}`, `/api/detener {seccion, n}` | Sí | Motor continuo. `dir` es 1 o −1. Un `detener` nunca se descarta. |
| `POST /api/paso {seccion, grados}` | Sí | Cambia `angulos`. Ninguna sección lo usa hoy. |
| `POST /api/pacientes/lista`, `guardar`, `borrar` | Admin | Registros de pacientes |
| `POST /api/pacientes/excel {ids}` | Admin | Devuelve un `.xlsx` (`registros-AAAA-MM-DD.xlsx`) con esos registros en ese orden. La página manda los que se ven en la tabla, con la búsqueda aplicada. Lo arma `web/excel.py` solo con la biblioteca estándar (zipfile + XML). DPI y teléfonos van como texto y las fechas como fechas. Se anota cuántos se descargaron, sin datos. |
| `POST /api/manual {tipo}` | Sí | PDF de `web/manuales/`. Con `usuario` devuelve `manual-usuario.pdf` a cualquiera con sesión; con `tecnico` devuelve `manual-tecnico.pdf` solo a un admin (otro rol: 403). Si falta el archivo avisa "todavía no está disponible". Se lee en cada descarga, así que basta reemplazar el archivo. Lo usa el botón "Manuales" del encabezado (`vistas/manuales.js`). Los PDF se suben al repo. |
| `POST /api/usuarios/lista`, `rol`, `activo`, `clave`, `borrar` | Admin | Perfiles. El propio no se toca, así siempre queda un administrador. Desactivar o borrar cierra su sesión. |

- **Tablet de control ("Recordar este equipo"):**
  - **Llave:** la casilla del login guarda una llave en `localStorage` (`llave-equipo`). En la tabla `llaves` de `camilla.db` solo queda su huella sha256, y hay a lo más una por perfil.
  - **Vuelve a entrar sola** con `/api/reanudar` cuando la sesión ya no existe: Android cerró la pestaña o se reinició la Raspberry.
  - **Al despertar** (`visibilitychange`) o al reconectar, consulta en el acto y retoma el control solo si está libre (`retomarControl` en `recepcion.js`). Si otro lo tiene, se respeta y hay que pedirlo como siempre.
  - **Sigue valiendo "un perfil, una sesión":** entrar con el mismo perfil en otro equipo saca a la tablet y anula su llave, así no rebota.
  - **Si otro cerró la sesión** (otro equipo o pestaña, perfil desactivado o borrado), `/api/estado` trae `cerrada` con el motivo. La página lo muestra y **no** vuelve a entrar sola, porque dos pestañas con la misma llave se sacarían entre sí sin parar. Solo vuelve a entrar sola cuando el servidor no conoce el token: se reinició o venció.
  - **PIN (`vistas/pin.js`, `/api/pin/abrir|crear|cerrar|seguir`):** en un equipo recordado de un **admin**, Registros y Usuarios se abren con un PIN de 4 números. Mover la camilla nunca lo pide.
    - **Crear:** se crea la primera vez que se abre Registros tras entrar con contraseña. Si la sesión entró con la llave, crearlo pide también la contraseña ("¿Olvidaste el PIN?").
    - **Dónde se guarda:** cifrado en `llaves.pin` (columnas agregadas el 23-11 con `ALTER TABLE`). Un login nuevo con "Recordar" crea llave nueva sin PIN.
    - **Cierre:** a los 30 min sin tocar nada en esas pestañas, al apagarse la pantalla o al volver a Control. Se borran los datos de la página.
    - **El servidor lo hace cumplir:** `abierto_hasta` en la sesión, 31 min, se renueva con cada pedido de admin y con `/api/pin/seguir`. Sin abrir, `/api/pacientes/*` y `/api/usuarios/*` responden `{ok:false, bloqueado:true}`.
    - **Intentos:** con 5 fallos hay espera de 60 s, que se duplica en cada tanda hasta 1 h. Cuenta por equipo (`camilla.intentos_pin`), así recargar no da intentos nuevos.
    - **Qué ve la página:** `/api/estado` trae `registros: {pin, abierto, pide_clave}`, o `null` si el equipo no usa PIN.
  - **Lo que no cambia:** el hombre muerto, el paro y `TIEMPO_LIBERAR`.
- **Hora (`web/reloj.py`):** la Pi no tiene internet ni pila de reloj y arranca con la hora en que se apagó.
  - Login, registro y reanudar mandan `hora: Date.now()`. Si la diferencia pasa de 2 min, el servidor guarda un desfase (se descartan horas anteriores a 2026).
  - Todo lo que guarda fecha usa `reloj`: `basedatos.ahora()`, la edad y la fecha del Excel, las llaves y `anotar()`.
  - No cambia la hora del sistema, porque la página corre sin root. Las horas propias de `journalctl` siguen siendo las de la Pi. Para eso haría falta un RTC (DS3231).
  - **Configuración de la tablet (Android):** dejarla cargando y activar "Pantalla activa mientras carga" en Opciones de desarrollador. En la red Camilla elegir "Mantener conexión" aunque no tenga internet. Quitar la optimización de batería a Chrome y fijar la app.
- **Ficha en PDF:** no pasa por el servidor. El botón "Descargar" de la ficha copia la ficha a `#hojaImpresion` y llama a `window.print()`. Con `body.imprimiendo`, la regla `@media print` de `admin.css` deja solo esa hoja. Al terminar (`afterprint`, o al cerrar la ficha) se vacía.
- JSON de más de 4096 bytes (64 KB en `/api/pacientes/excel`) o que no sea un objeto: 400. Sin sesión: 401. Sin rol de administrador: 403.
- **Portal cautivo:** una petición que llega a 10.42.0.1 con otro `Host` (por ejemplo `captive.apple.com`) recibe un 302 a `http://10.42.0.1:8000/`, y el celular abre la página solo.
  - Excepción: la prueba de internet de Android (`/generate_204`, `/gen_204`) recibe un 204 si viene de la IP de un equipo recordado usado en los últimos 60 min (`es_equipo_recordado`). Así la tablet no muestra "sin internet". Solo a ella: un celular que creyera tener internet dejaría de usar sus datos móviles. La tablet Huawei (Android 7) ignora `captive_portal_mode` por `adb`.
- **Login:** PBKDF2 fuera del candado; con contraseña incorrecta espera 1 s. Perfil desactivado: no entra.
- **Registro del sistema:** `anotar()` escribe a stderr con la hora (`journalctl -t python3` con el arranque automático). No anota las rutas de `SILENCIO` ni datos de pacientes, solo su número. `encender_red.sh` filtra estas frases: `inicio sesion`, `cerro sesion`, `creo su perfil`, `control: `, `el control a `, `PARO` y `contrasena incorrecta`.

### `web/paginas.py`

Compone `plantillas/index.html` resolviendo cada `<!-- incluir: ruta -->` en cada visita (al editar basta con recargar) y entrega solo `.css`, `.js` y `.woff2` de `publico/`. `camilla.db` y el código quedan fuera.

## 5. Base de datos: `web/basedatos.py`

- `web/camilla.db`, creada con permiso 600. Está en `.gitignore` porque tiene datos de pacientes y el repositorio es público.
- **`usuarios`:** `id`, `usuario` (único, sin distinguir mayúsculas), `nombre`, `rol` (`admin` o `fisio`), `activo`, `sal`, `clave` (PBKDF2-HMAC-SHA256, 300 000 vueltas, sal de 16 bytes) y `creado`.
- **`pacientes`:** todos los campos opcionales, pero hay que llenar al menos uno: nombres, apellidos, sexo (F/M), nacimiento, DPI, carné, teléfono, correo, contacto de emergencia y su teléfono, estatura (m), peso (lb), fisioterapeuta, diagnóstico, dolor (EVA de 0 a 10), próxima cita (`AAAA-MM-DD HH:MM`) y notas, más `creado` y `creado_por`.
- La única migración es la de `pacientes` de antes del 12-11 (nombre y edad). Una columna nueva no llega sola a una base ya creada.
- **Reglas** (las aplica el servidor; la página repite las mismas en `ui/formularios.js`, `vistas/acceso.js` y `vistas/pacientes.js`):
  - Nombre: solo letras, de 2 a 40, sin espacios ni tildes. Usuario: minúsculas y números, de 3 a 20. Contraseña: letras y números, de 6 a 100.
  - DPI de 13 números, teléfonos de 8, correo con `@` y punto, nacimiento no futuro y de menos de 120 años, estatura de 0.30 a 2.50 m, peso de 1 a 900 lb, dolor entero de 0 a 10, diagnóstico hasta 1000 caracteres y notas hasta 2000.
- **Terminal:** `python3 web/basedatos.py` lista los perfiles; `admin USUARIO` lo hace administrador; `clave USUARIO` le pone otra contraseña; `revisar` solo avisa si falta un administrador.
- `web/datos_prueba.py` agrega 20 pacientes inventados (`creado_por = "datos-de-prueba"`), y con `borrar` quita solo esos.

## 6. Página: `web/plantillas/` y `web/publico/`

Sin compilación: el servidor junta las plantillas y el navegador carga módulos ES, sin dependencias circulares. Bootstrap 5.3.3 y las fuentes (Barlow Condensed, IBM Plex) están en `publico/vendor/`, porque la red no tiene internet. Los módulos leen el DOM al cargarse: quitar un `id` del HTML rompe el módulo que lo usa.

| Módulo (`publico/js/`) | Qué hace |
|---|---|
| `config.js` | `CONFIG` de cada sección, `RITMO` y tiempos |
| `estado.js` | Estado compartido (`panel`, `control`, `sesion`) y `puedeMover()` |
| `recepcion.js` | Aplica cada respuesta de `/api/estado` |
| `api/cliente.js`, `sondeo.js`, `ordenes.js`, `admin.js` | Peticiones, consulta cada 1 s, órdenes y pedidos de administración |
| `camilla/movimiento.js` | Botón sostenido, estimación, "Ir a" y paro |
| `camilla/mandos.js` | Eventos de los botones, Esc, Plano y Bloquear |
| `camilla/telemetria.js` | `aplicarAngulos` y la API `window.camilla` |
| `ui/pintado.js`, `ui/dibujo.js` | Pantalla y dibujo SVG; nunca mandan órdenes |
| `ui/modales.js`, `avisos.js`, `formularios.js`, `registro.js` | Modales, toasts, ayudas de formularios y "Registro de comandos (desarrollo)" |
| `vistas/acceso.js`, `sesion.js`, `cesion.js`, `pestanas.js`, `pacientes.js`, `usuarios.js` | Login y registro, entrar y salir, pasar el control, pestañas por rol, pacientes y perfiles |

**`config.js` hoy:**

| Sección | Escala | Paso cada 70 ms | Opciones |
|---|---|---|---|
| `altura` | 0 a 100, sin número en pantalla | 2 | `continua`, `sinTope`, `numerica: false` |
| `cabeza` | −30° a 70° | 1° | `continua`, `sinTope` |
| `piernas` | 0° a 45° | 1° | `continua`, `sinTope` |

- `continua`: el motor corre mientras se mantiene el botón (`/api/mover`), y la telemetría del servidor no toca esa sección. Sin `continua`, la sección mandaría un `/api/paso` por grado; no la usa ninguna.
- `sinTope`: la estimación nunca corta el movimiento ni deshabilita el botón al llegar al límite. El motor sigue hasta que se suelta o hasta el tope interno del actuador.
- Tiempos: `CONSULTA_MS` 1000, `FALLOS_PARA_CAIDA` 3, `MANTENER_MS` 400, `ESPERA_SOLICITUD` 30 y `ESPERA_RESPUESTA` 30. Plazos de las peticiones: 2.5 s para el estado, 8 s para login y registro, 5 s para lo demás.

**Cómo se comporta hoy:**

- **Estimación:** la página arranca con cabeza y piernas en 0° y la altura a media barra. Mientras se mantiene un botón suma un paso cada 70 ms: Cabeza llega de 0° a 70° en 4.9 s y Piernas a 45° en unos 3 s, pero el actuador de Cabeza tarda unos 30 s en recorrer sus 150 mm y el de Piernas unos 25 s en sus 250 mm. Las otras pantallas no ven el cambio, y al recargar vuelve a 0°.
- **Un toque** manda `mover` y enseguida `detener`: el motor se mueve una fracción de segundo y el número sube 1°. Los textos "Un toque = 1°" y los `+1°`/`−1°` de los botones ya no corresponden.
- **"Ir a" y "Plano 0°"** corren en la página (un paso cada 90 ms) y, con secciones `continua`, no mandan ninguna orden: solo cambian el número y el dibujo, mientras la tarjeta se ilumina y el estado dice "Ajustando a ...".
- **Una sección a la vez:** `iniciarManual` detiene lo que estuviera en marcha antes de arrancar otra, y el servidor y `hardware.py` guardan un solo motor.
- **Botones:** se deshabilitan sin control, con paro, con bloqueo, sin conexión, sin ESP32 o si el ESP32 no informa esa sección (aparece "Sin actuador").
- **Hombre muerto en la página:** soltar en cualquier parte, `pointerleave`, `pointercancel`, perder el foco u ocultar la página detienen el movimiento. Salir de la pestaña Control también.
- **Paro:** el botón rojo alterna entre activar y liberar, sin confirmación. Esc lo activa, salvo en los formularios del administrador. Hay un paro flotante en el login, sobre los modales y fuera de la pestaña Control.
- **Bloquear** deshabilita el movimiento solo en esa pantalla.
- **Sin conexión:** tras 3 consultas fallidas seguidas, detiene el movimiento, muestra "Sin conexión con la camilla" y bloquea. Sin ESP32: la cinta "Sin conexión con los motores" y el estado del mismo nombre.
- **Sesión:** el token va en `sessionStorage`: cada pestaña cuenta como un dispositivo, y recargar no pide entrar otra vez.
- **Roles:** el fisioterapeuta solo ve Control; el administrador ve Control, Registros y Usuarios.
- **Pedido de control:** quien pide ve 30 s de espera; el titular tiene 30 s para decidir y, si no responde, se rechaza solo.
- `window.camilla` expone `aplicarAngulos`, `topeAltura`, `estado`, `irA` y `paro` para probar desde la consola del navegador. Ningún dato del servidor llama a `topeAltura`.

## 7. Red y arranque automático: `red/`

| Script | Qué hace |
|---|---|
| `instalar_red.sh` | Una vez, con internet y `sudo`: instala hostapd y crea `/etc/hostapd/camilla.conf` (permiso 600). Red `Camilla`, Guatemala, canal 6, 802.11n, WPA2-PSK con CCMP y PMF apagado. Pide la clave (8 caracteres o más) o conserva la que ya había. Se usa hostapd porque NetworkManager agrega WPA3, que el chip de la Pi 4 maneja mal. |
| `encender_red.sh` | Encendido a mano, sin `sudo` delante. Suelta `wlan0` de NetworkManager, pone 10.42.0.1/24, enciende hostapd y dnsmasq (DHCP 10.42.0.10–254, y todo nombre responde 10.42.0.1), redirige el puerto 80 al 8000 con nft y arranca `servidor.py`. Muestra quién se conecta; ENTER apaga todo, vuelve al WiFi anterior y guarda `~/reporte_red.txt`. No hace nada si el arranque automático está activo. No lanzarlo por SSH sobre WiFi: corta el SSH y, al morir la sesión, se apaga. |
| `instalar_arranque.sh` | `sudo ./instalar_arranque.sh` crea y activa dos servicios: `camilla-red` (root; copia `arranque_red.sh` a `/usr/local/sbin/camilla-red`; se reinicia a los 5 s si falla) y `camilla-pagina` (el usuario que instaló, grupo `dialout`, `python3 -u servidor.py` en `web/`, sin `--simulador`; se reinicia siempre a los 3 s). No los enciende al instalar. `quitar` los borra. |
| `arranque_red.sh` | Lo usa `camilla-red`: `iniciar` espera hasta 30 s a `wlan0` y hace lo mismo que `encender_red.sh`, sin monitor; `apagar` le devuelve el WiFi a NetworkManager. |

Detener un rato: `sudo systemctl stop camilla-pagina camilla-red` (al reiniciar vuelven). Que no arranquen: `disable`. Estado: `systemctl status camilla-red camilla-pagina`. Mensajes del servidor: `journalctl -t python3 -f`. Mientras la laptop esté en la red Camilla, no tiene internet.

## 8. Hardware

**Actuadores** (12 V, con tope interno en los dos extremos, sin sensor de posición):

| Sección | Modelo | Carrera | Velocidad | Corriente |
|---|---|---|---|---|
| Cabeza (2) | ECO-WORTHY 3000N | 150 mm (6") | 5 mm/s | 3 A máxima |
| Piernas (2) | 1500N | 250 mm (10") | 10 mm/s | 4 A |
| Altura | NEMA 17 (200 pasos/vuelta) con DRV8825 | Según el husillo (sin medir) | 1000 pasos/s = 5 vueltas/s | Según la etiqueta; Vref = corriente / 2 |

- No mezclar modelos en una sección: uno iría al doble de velocidad y torcería la estructura.
- El tope interno protege al actuador, no a la estructura. Montado, hay que soltar antes de que la camilla llegue a su límite.
- Con 2 actuadores por sección y sin sensores pueden desincronizarse un poco; se corrige solo al llegar a un extremo, por el tope interno.
- El de Piernas trae un interruptor de polaridad que no se usa.

**Fuente de motores:** 12 V, 40 A, con varios pares de bornes V+ y V−.

**Conexiones conocidas al 16-11** (confirmar con el usuario si cambió algo):

- **Piernas en el MD-BTS7960:** RPWM a GPIO 26, LPWM a GPIO 27, R_EN y L_EN a 3.3 V, VCC a 3V3 y GND al GND del ESP32. Los 2 actuadores en paralelo: M+ a sus cables A y M− a sus cables B. R_IS y L_IS sin conectar (pueden pasar de 3.3 V). En estas placas el GND de control y B− suelen estar unidos: comprobarlo con el multímetro.
- **Cabeza en el L298N** (provisional, aguanta unos 2 A por canal): IN1 a GPIO 18, IN2 a GPIO 19, jumper de ENA puesto, OUT1 y OUT2 al actuador. 12 V con fusible de 3 A; GND a V− y al GND del ESP32; el 5V sin conectar, con el jumper del regulador puesto. Revisar que traiga sus 8 diodos y tocar el disipador al probar.
- **Altura en el DRV8825** (placa morada con disipador; los pines tienen nombres de clon: STP, 1A/2A/1B/2B): STP a GPIO 25, DIR a 33, EN a 13, RST y SLP puenteados a 3.3 V. Fuente de 12 V solo a VMOT/GND, con un capacitor en VMOT (100 µF según `prueba_stepper.py`; en la guía se usó 1000 µF). Motor en 1A/2A y 1B/2B. Corriente = Vref × 2. Nunca conectar o desconectar el motor con la fuente encendida.
  - En la protoboard del usuario (disipador arriba, filas 18 a 25): a la izquierda GND, FLT, 2A, 1A, 1B, 2B, GND y VMOT; a la derecha DIR, STP, SLP, RST, M2, M1, M0 y EN.
  - Al 16-11 el stepper no se mencionó como conectado. El ESP32 igual informa `altura`, así que la página deja usarla aunque no haya motor.

**Definitivo (aprobado):** un MD-BTS7960 (43 A, 5.5 a 25 V) por sección, con los dos actuadores en paralelo.

- Fusible retardado, uno por módulo, en B+: Cabeza 7.5 A y Piernas 10 A, de vidrio 6 × 30 mm, con portafusible en línea de 15 A o más. Si se funde, paran los dos actuadores juntos.
- Cable de 14 AWG para B+ y B−, y de 16 AWG a los actuadores.
- Sin TVS al principio: no hay contactos que chispeen y el módulo trae diodos internos.
- Si EN va a un GPIO, resistencia de 10 kΩ de EN a GND, para que quede apagado mientras arranca el ESP32.
- El BTS7960 de Cabeza usaría los mismos GPIO 18 y 19 como RPWM y LPWM.

**Relés (solo historia):** el módulo de 4 relés SPDT se usó el 09-11. El firmware conserva `MODULO = "reles"` (cabeza con 26/27 y 25/33, activo en bajo). No sirve a la vez que los puentes, porque comparte pines.

**Pines del ESP32:**

| Uso | GPIO |
|---|---|
| Ocupados | 26, 27 (piernas); 18, 19 (cabeza); 25, 33, 13 (altura); 2 (LED); 1 y 3 (USB con la Raspberry) |
| Reservados | 4 y 35: finales de carrera de la altura (abajo y arriba) |
| Libres | 14, 16, 17, 21, 22 (21 y 22, mejor para I2C), 23, 32, 34, 36 y 39. Del 34 al 39 son solo de entrada y no tienen resistencia interna. |
| No usar | 6 a 11 (memoria). Evitar 0, 5, 12 y 15, que son de arranque. |

**Lista de compra pendiente:** fusibles 6 × 30 mm retardados (3 de 7.5 A y 3 de 10 A), 2 portafusibles en línea de 15 A o más, 2 resistencias de 10 kΩ, 2 BTS7960 y cable de 14 y 16 AWG. De la tienda **no sirven**: TVS de 3.3, 5, 9 o 12 V (conducen a 12 V y queman el fusible), SMBJ170CA y 1.5KE200CA (no actúan), SM12C (es para datos), ni un 1N4007 entre los cables del actuador (hace corto al invertir).

## 9. Problemas conocidos

**Seguridad** (comprobados en el código, sin resolver):

1. **No hay paro físico** que corte la fuente de los motores sin depender de ninguna placa. Sin eso no se debe probar con personas.
2. El paro se libera con un segundo toque: el botón alterna sin confirmar.
3. El paro se libera sin sesión, y `POST /api/paro {}` también lo apaga.
4. El paro vive en memoria: reiniciar el servidor (o que systemd lo reinicie) lo borra.
5. El hombre muerto del servidor para entre 1.0 y 1.5 s; el ESP32 para en 0.5 s si deja de recibir.
6. Con `sinTope` y sin sensores, nada impide que un actuador empuje contra la estructura si se mantiene el botón: solo lo frena su tope interno.
7. No hay tiempo máximo de marcha por sección.

**Lo que la pantalla muestra y no es cierto:** grados y barra de altura estimados; "Ir a" y "Plano 0°", que no mueven nada pero dicen "Ajustando a ..."; "Un toque = 1°" y `+1°`/`−1°`. Cada pantalla tiene su propia estimación.

**Hardware y conexión:**

- **Ruido en el USB con motores** (09-11, con relés): con solo los relés, 0 errores en 1 minuto; con actuadores, 5. El kernel registró `cp210x ttyUSB0: usb_serial_generic_read_bulk_callback - urb stopped: -32`, y después Linux deja de leer el puerto hasta reabrirlo. `hardware.py` lo reabre solo (`99a91cf`), pero cada corte detiene el movimiento unos segundos. Con el BTS7960 se espera menos ruido. **Falta contar los errores con los puentes H y la red Camilla.** La reapertura solo se probó con un puerto simulado.
- **Thonny a veces no detiene el programa** ("Device is busy"): si la placa ya recibió órdenes, el watchdog está activo. Funciona apagar el servidor, presionar EN para un arranque limpio y luego Stop. Si falla, `mpremote`.
- La Raspberry nunca marcó voltaje bajo con el ESP32 alimentado por su USB.

**Menores:**

- Registro de perfiles abierto: con la clave del WiFi cualquiera crea un perfil y mueve la camilla.
- HTTP sin cifrar, con datos de salud. El servidor escucha en todas las interfaces: también responde por cable o por otro WiFi si la Raspberry está conectada.
- Sin límite de intentos por IP (solo la espera de 1 s).
- Rechaza nombres como `José`, `Peña` o `Ana Lopez`, y contraseñas con símbolos.
- La Pi no tiene reloj propio ni NTP en la red Camilla: las fechas pueden salir mal.
- Cargar la página hace 49 peticiones. En la Pi no se ha medido.
- `GUIA.md` e `INTEGRACION.md` no incluyen `esp32/`, `hardware.py`, `--simulador`, `n`, `hardware` en `/api/estado`, `python3-serial`, la reapertura del puerto ni el stepper, siguen nombrando `SIMULACION` (ya no existe) y dicen "Un toque = 1°" y que no hay ESP32.

**Conservar:** entrega de archivos limitada a `publico/`, SQL parametrizado, roles validados en el servidor y la máquina de estados del control.

## 10. Lo que falta para terminar

**Decisiones del usuario:**

1. **Pantalla sin sensores:** seguir con grados estimados, pasar a SUBIENDO / BAJANDO / EN REPOSO, o poner sensores. En cualquier caso hay que decidir qué pasa con "Ir a", "Plano 0°" y los textos de 1°.
2. **Sensores de ángulo:** si se ponen y cuál. El 11-11 el usuario eligió para Piernas un encoder óptico absoluto en código Gray, de 0° a 90°, hecho por él (en la rama `backup-cambios-esp32`, sin piezas reales). Recomendación anterior: B10K para probar; WDD35D4 o el encoder para el final; nada incremental con pacientes. Análisis completo en `git show 1eaf7a2:CONTEXTO.md`.
3. **Perfiles:** registro abierto o que los cree el administrador.
4. **Registro de uso:** solo cuentas y pacientes, o también un historial de quién movió la camilla y cuándo.
5. **Altura:** qué husillo lleva (mm por vuelta) y si el NEMA 17 aguanta la camilla con una persona. Si no, NEMA 23 con reductor o actuador lineal con BTS7960. Si el husillo no es autobloqueante (paso largo, como T8×8), la camilla baja sola al cortar la energía: hace falta husillo de paso fino, freno o reductor.
6. Si se deja la sección 11 de `INTEGRACION.md` en un documento que se va a evaluar.

**Software que se puede hacer ya:**

- Arreglo del paro (propuesta en la sección 13).
- Finales de carrera de la altura en `main.py` (GPIO 4 y 35, como en `prueba_stepper.py`), informados en la línea `E` y mostrados en la página (`topeAltura`).
- Tiempo máximo de marcha por sección en el ESP32.
- Textos de la pantalla que no corresponden.
- Bajar `HOMBRE_MUERTO` o revisar el servidor más seguido.
- Aceptar tildes, ñ y espacios en los nombres.
- Actualizar `GUIA.md` e `INTEGRACION.md`.
- Volver a armar las pruebas en simulación: los scripts del 09-11 al 11-11 (`falsos.py`, `probar_*.py`) se perdieron con las carpetas temporales. Conviene guardarlos en el repositorio.

**Hardware:**

- BTS7960 de Cabeza y su segundo actuador.
- Paro físico: hongo con contactor que corte la fuente de motores.
- Altura con carga: mantener Subir 5 s y medir los mm. Si zumba, se atora o baja solo, `PASOS_VELOCIDAD` a 800 o 600.
- Calibrar la estimación de Cabeza y Piernas cuando estén montadas.
- Contar los errores USB con motores, en la red Camilla.
- Proteger `camilla.db` contra cortes (la Raspberry arranca desde una memoria USB): copias o UPS. Reloj DS3231.

## 11. Comandos

**La terminal del PC es Git Bash:** las rutas van con `/`; con `\`, Bash se las come.

```bash
python web/servidor.py                   # con ESP32 por USB
python web/servidor.py --simulador       # sin placa; las 3 secciones simuladas
python web/basedatos.py admin USUARIO    # primer admin, después de crear el perfil en la página
python web/datos_prueba.py               # 20 pacientes inventados (quitarlos: python web/datos_prueba.py borrar)
```

Se abre en `http://localhost:8000`; desde otro equipo, `http://IP-DE-LA-RASPBERRY:8000`. Si el ESP32 no se detecta solo: variable `CAMILLA_PUERTO` (por ejemplo `COM5`).

**Subir desde el PC** (solo si el usuario lo pide; nunca `git add .`, por `compi.txt`):

```bash
git add esp32 web red CONTEXTO.md        # y GUIA.md o INTEGRACION.md si cambiaron
git commit -m "..."
git push origin desarrollo-final
```

**Bajar en la Raspberry** (necesita internet; con el arranque automático está en la red Camilla, sin internet):

```bash
sudo systemctl stop camilla-pagina camilla-red     # vuelve a su WiFi
cd ~/Desktop/Camilla
git fetch && git checkout desarrollo-final && git pull
sudo systemctl start camilla-red camilla-pagina    # o solo: sudo systemctl restart camilla-pagina
```

**Volver a encender la red Camilla estando por SSH.** Al encenderla, el WiFi de la Pi deja internet y el SSH por WiFi se corta (es normal). `--no-block` deja el encendido en manos de systemd, así sigue aunque se corte la conexión:

```bash
sudo systemctl start --no-block camilla-red camilla-pagina
```

Después: conectar la laptop a la red **Camilla** y entrar de nuevo con `ssh diegocardona@10.42.0.1`. Ahí se revisa que la página arrancó (debe decir `Pagina en http://localhost:8000`):

```bash
systemctl is-active camilla-red camilla-pagina      # los dos: active
journalctl -t python3 -n 20 --no-pager
```

**Cargar el ESP32 por SSH con `mpremote`** (sin Thonny ni pantalla), con la página apagada. `camilla-pagina` se reinicia sola: un `pkill` no basta.

```bash
sudo apt install -y pipx && pipx ensurepath && pipx install mpremote     # una vez, con internet
sudo systemctl stop camilla-pagina 2>/dev/null; pkill -f servidor.py
~/.local/bin/mpremote connect /dev/ttyUSB0 cp esp32/main.py :main.py
~/.local/bin/mpremote connect /dev/ttyUSB0 reset
sudo systemctl start camilla-pagina
```

**Cargar el ESP32 con Thonny** (también está en la Raspberry):

1. Apagar el servidor: Thonny y el servidor no pueden usar el USB a la vez.
2. Intérprete MicroPython (ESP32) y Stop hasta ver `>>>`.
3. View → Files → `.../esp32/main.py` → clic derecho → **Upload to /**. El 09-11, "Guardar como" pareció funcionar pero no reemplazó el archivo de la placa.
4. Comprobar en la consola: `import os; print([(n, "camilla lista" in open(n).read(), "Conectando" in open(n).read()) for n in os.listdir() if n.endswith(".py")])`. Lo correcto es `[('boot.py', False, False), ('main.py', True, False)]`.
5. Presionar EN: debe salir `# camilla lista`. Si sale `Conectando a ...`, sigue el programa del compañero.

**Diagnóstico en la Raspberry:**

```bash
uptime -s; vcgencmd get_throttled; ls -l /dev/serial/by-id/     # reinicio, voltaje bajo (0x0 = bien), ESP32 visto
journalctl -k --no-pager --since "2 min ago" | grep -cE "urb stopped|USB disconnect"   # errores USB tras una prueba
journalctl -t python3 -f                                         # mensajes del servidor
sudo fuser -v /dev/ttyUSB0                                       # quién tiene el puerto
```

El 09-11 quedaron corriendo dos registros en segundo plano (`~/monitor_kernel.txt` y `~/monitor_voltaje.txt`). Para detenerlos: `pkill -f "vcgencmd get_throttled"` y `pkill -f "journalctl -kf"`.

**Preparar otra Raspberry** (con internet, desde la carpeta del proyecto):

```bash
python3 --version                                       # 3.8 o mayor
python3 -c "import serial; print(serial.__version__)"   # si falla: sudo apt install -y python3-serial
id -nG | grep -w dialout                                # si no sale: sudo usermod -aG dialout $USER && sudo reboot
command -v hostapd dnsmasq nft nmcli                    # si falta: sudo apt install -y hostapd dnsmasq-base nftables network-manager
sudo test -e /etc/hostapd/camilla.conf && echo Lista    # si no: cd red && sudo ./instalar_red.sh
cd red && sudo ./instalar_arranque.sh                   # arranque automático
```

Si `/dev/ttyUSB0` aparece y desaparece: `sudo apt remove -y brltty`. No copiar los `.sh` desde Windows: quedarían con CRLF.

## 12. Raspberry real

- Usuario `diegocardona`. Carpeta del proyecto: **`~/Desktop/Camilla`** (confirmado el 23-11).
- **Rama instalada: `desarrollo-final`** (`0373ed3`, 23-11). Antes tenía `muestra-citein`, la de la presentación del 13-11. Para volver a ella: `git checkout muestra-citein` y reiniciar `camilla-pagina`. Entre las dos ramas, `esp32/` y `red/` son iguales: no hace falta volver a cargar el ESP32.
- Python 3.13, pyserial 3.5, permiso `dialout`, hostapd, dnsmasq, nft y nmcli instalados. Red Camilla y arranque automático instalados y funcionando (12-11).
- El ESP32 aparece como `CP2102` (`10c4:ea60`) en `/dev/ttyUSB0`.
- Se usa con pantalla, teclado y mouse USB, y por SSH desde la laptop.
- **WiFi Meso:** IP por DHCP (fue `172.17.71.64`). Meso saca a la Raspberry cada 30 s más o menos (`WNM: Disassociation Imminent`) y se cae el SSH; no es falla de la Raspberry. Para SSH estable, cable de red.
- El registro del sistema no es persistente: reiniciar borra la evidencia, incluido `vcgencmd get_throttled`.
- `Connection closed by ... port 22` suele significar que la Raspberry se está reiniciando.
- El USB-C de la Pi 4 es solo de alimentación.

## 13. Decisiones y propuestas

**Tomadas:**

- El administrador controla la camilla y ve los registros.
- Raspberry y ESP32 por USB serie con `pyserial`. WebSocket, después.
- Red local propia, sin internet. Arranque automático con systemd (12-11).
- Cabeza con los 2 actuadores 3000N y Piernas con los 2 de 1500N.
- Definitivo: un BTS7960 por sección, con los actuadores en paralelo y un fusible retardado por módulo.
- Altura con NEMA 17 y DRV8825 (13-11).
- El servidor reabre el puerto si el ESP32 se queda mudo (`99a91cf`).
- `compi.txt` no se agrega a `.gitignore` y no se sube.

**Propuesta del paro (sin aprobar):** el botón rojo solo activa; liberar va aparte, con confirmación y con sesión; `POST /api/paro` sin `activo` booleano responde 400; el paro se guarda en SQLite para que sobreviva a un reinicio.

**Otras propuestas (sin aprobar):** `wlan0` fijo, watchdog de la Pi, copias de `camilla.db` o UPS, reloj DS3231, dos administradores y una hoja junto a la camilla con cómo reiniciar. Más adelante, R_IS y L_IS del BTS7960 podrían detectar un atasco, con divisor a 3.3 V.

**FastAPI y WebSocket (12-11):** no son alternativas: FastAPI es el framework y WebSocket la forma de comunicación. Si se mejora, empezar por WebSocket solo para avisos (estado, paro y pedidos de control) con `aiohttp` (`apt install python3-aiohttp`) en el mismo puerto, y mantener `POST /api/paro` como segunda vía. El hombre muerto igual necesita su latido. FastAPI, solo si el proyecto crece.

## 14. Guías publicadas

Privadas de la cuenta del usuario. Algunas muestran planes viejos (por ejemplo, el cableado BTS7960 tiene Cabeza en 25/26/27 y Piernas en 18/19/21): manda este archivo.

- Puesta en marcha: https://claude.ai/artifact/HghKdvTRKGM1bepkxkPx92
- Plan general de integración: https://claude.ai/artifact/6Yo3eoRURGcjXuc5KChWrS
- Cableado con relés, fusibles y TVS: https://claude.ai/artifact/1Gk6CeN5LLnTMpQpNV2bqg
- Cableado final con BTS7960: https://claude.ai/artifact/BPPDzhjXEg8qiHQrK63hmF
- Encoder de piernas: https://claude.ai/artifact/MAu8PJ5JfVQvSUGJZH4XQU
- Stepper de la altura (DRV8825, Vref, micropasos): https://claude.ai/artifact/AW9F4AJEpPeUgS7757k2Cr
- Puente H de las piernas (BTS7960 con 2 actuadores): https://claude.ai/artifact/1vXRyzqTNfADsvsiMQrvpW

## 15. Para la próxima Claude

- Responder en español. Lo que escribe el usuario manda sobre las guías.
- Trabajar en `desarrollo-final`. No tomar otras ramas como referencia salvo que el usuario lo pida.
- Decir si algo se puede y cómo antes de modificar, salvo que lo pida directo.
- No hacer commit ni push sin que lo pidan. Nunca `git add .`: el repositorio es público y `compi.txt` tiene la clave del WiFi.
- No crear ni editar `CLAUDE.md`: el usuario prefiere este archivo.
- `web/camilla.db` tiene datos de pacientes: no se sube. Para probar, datos inventados (`datos_prueba.py`).
- `GUIA.md` e `INTEGRACION.md` describen solo lo que existe, sin hipótesis ni planes.
- Desde el PC, nada de red o hardware se da por probado.
- Python 3.8+ y solo biblioteca estándar, salvo `pyserial`. El firmware es MicroPython: sin f-strings ni funciones que no existan allí.
- El usuario prefiere manejar todo desde la página antes que pruebas sueltas en Thonny: lo nuevo se integra a `main.py` y se prueba con la página.
- **Al guiar en el hardware:** pasos numerados que digan dónde se hace cada uno (terminal SSH, pantalla de la Raspberry, Thonny, la mesa o el chat), pidiendo la salida en cada punto de control.
- Antes de concluir que la Raspberry se reinició sola, preguntar si la reinició el usuario. Ante algo raro, pedir que no reinicie ni desconecte hasta capturar `uptime -s`, `get_throttled` y `journalctl`.
- Para probar sin tocar el repositorio: copiar `web/` y `esp32/` a una carpeta temporal, sin `camilla.db`. El firmware corre en CPython con módulos falsos `machine` (`Pin`, `PWM`, `WDT`, `reset`) y `time` (`ticks_ms`, `ticks_diff`, `ticks_add`, `sleep_ms`), y `hardware.serial` se reemplaza por un puerto falso conectado a él.

**Trampas del código:**

- `esp32/main.py` decide qué secciones existen: las informa en cada línea `E`, y la página muestra "Sin actuador" para las que falten.
- `hardware.py` guarda una sola orden y el servidor un solo `motor`: hoy no se pueden mover dos secciones a la vez.
- `aplicarAngulos` (`camilla/telemetria.js`) ignora las secciones `continua`. Si llegan ángulos reales, hay que cambiar esa condición y la de `darPaso` (`if (!c.continua)`).
- `LIMITES` (`servidor.py`) y `CONFIG` (`config.js`) se cambian juntos, igual que las reglas de `basedatos.py`, `ui/formularios.js`, `vistas/acceso.js` y `vistas/pacientes.js`.
- `CONFIG.altura.numerica = true` rompe la página con un `TypeError`: la altura no tiene esos elementos en el HTML.
- Si se deshabilita un botón mientras se mantiene pulsado, puede no llegar el `pointerup`. Por eso existe `sinTope`.
- Una orden `detener` nunca se descarta, aunque su número sea viejo.
- Al abrir el puerto el ESP32 se reinicia: `ESPERA_ARRANQUE` (6 s) debe ser mayor que `SILENCIO_REABRIR` (3 s), o se queda reabriendo en bucle.
- `MODULO = "reles"` usa 25 y 33, los mismos de la altura: en ese modo no se crea la altura.
- `encender_red.sh` filtra el texto de `anotar()` y la línea `"GET / `: cambiar esas frases rompe su monitor.
- `ESPERA_SOLICITUD` es 35 s en el servidor y 30 s en la página, a propósito.
- `solicitud.usuario` y `respuesta.usuario` traen el nombre para mostrar, no el usuario.
- Los métodos de `Camilla` asumen `candado` tomado; SQLite, PBKDF2 y el puerto serie van fuera.
