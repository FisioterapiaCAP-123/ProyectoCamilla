# Contexto del proyecto

**Actualizado el 26-11-2026.** Rama `desarrollo-final`, creada el 20-11 desde `master` (`1eaf7a2`, del 16-11) para terminar el desarrollo. El 24-11 se revisó otra vez contra el código de esta rama, archivo por archivo (tablet de control, portal, finales de piernas, altura sin finales y sin `prueba_stepper.py`). El 25-11 se agregó la placa propia del ESP32 (sección 8). El 26-11 `main.py` pasó a los pines de la placa, y la placa pasó a la versión 2: cada MPU con su propio I2C y el motor de cabeza en 22 y 23 (sin probar en el hardware). Lo que no se puede comprobar desde el PC (hardware, Raspberry) viene de las notas anteriores, con la fecha en que se probó, o se marca "sin confirmar".

- La versión anterior de este archivo, con la historia del 09-11 al 16-11, el análisis completo de sensores de ángulo y el diseño del encoder, se ve con `git show 1eaf7a2:CONTEXTO.md`.
- **Otras ramas: no se usan como referencia**, salvo que el usuario lo pida. `manuales` (manuales de la tesis y un diseño con AS5600 sin montar), `muestra-citein` (interfaz sin grados de la presentación del 13-11), `backup-cambios-esp32` (encoder; tiene `codigoesp32.txt` con la clave del WiFi), `esp32-conexion` y `optimizaciones-esp32` (viejas).
- `GUIA.md` e `INTEGRACION.md` están desactualizadas: describen el sistema en simulación, sin ESP32 (ver la sección 9).

## 1. Estado en una mirada

| Parte | Estado |
|---|---|
| Control desde el celular | Funciona. El 13-11 las tres secciones se movieron desde la página con la placa real. |
| Piernas | 2 actuadores 1500N en paralelo en un BTS7960 (GPIO 13 y 27 desde el 26-11, por la placa propia; antes 26 y 27). Probado en la placa real el 11-11. Finales de carrera NC en GPIO 17 (arriba) y 16 (abajo), en `main.py` desde el 24-11; sin probar en la placa. |
| Cabeza | 1 actuador 3000N (de 2) en un L298N (GPIO 22 y 23 con la placa v2, desde el 26-11; antes 18 y 19). Probado en la placa real con 18 y 19. Faltan su BTS7960 y el segundo actuador. Finales previstos en GPIO 4 (arriba) y 32 (abajo), sin código; antes se pensaba en 23 para arriba. |
| Altura | NEMA 17 con DRV8825 (GPIO 25, 33 y 26 desde el 26-11; antes EN en el 13). Probado sin carga el 13-11 y desde la página el 24-11. **Sin finales de carrera** (decisión del 24-11): se mueve solo mientras se mantiene el botón. Husillo sin definir. Rama `mpu-angulos` (26-11, sin probar en la camilla): cuenta de pasos con topes y modo manual (pedal), sección 3. |
| Placa propia del ESP32 | Diseñada el 25-11 y rehecha el 26-11 (versión 2: cada MPU con su propio I2C). Una cara, 106 × 70 mm, para fresar en CNC. Sin fresar. Cambia 9 pines respecto a la protoboard (sección 8); `main.py` de `mpu-angulos` ya los usa. |
| Ángulos y altura en pantalla | Rama `mpu-angulos` (26-11, sin probar en la camilla): piernas con MPU6050, ángulo real y calibración desde la página (sección 3). Sin sensor calibrado, y siempre en la altura, el valor es una estimación de cada página. |
| Tablet de control | Funciona (23 y 24-11, Huawei con Android 7): "Recordar este equipo", PIN de Registros, pantalla completa, app fijada y sin aviso de "sin internet". |
| "Ir a" y "Plano 0°" | Solo mueven el número y el dibujo. No mueven motores. |
| Seguridad del movimiento | Hombre muerto en la página, el servidor y el ESP32; watchdog; órdenes numeradas; paro lógico. **No hay paro físico.** |
| Perfiles, roles y pacientes | Completo, en SQLite. Registro de perfiles abierto. Sin bitácora de uso. |
| Red Camilla y arranque automático | Instalados y funcionando en la Raspberry desde el 12-11. Portal: sin sesión la página se abre sola; con sesión el equipo se queda en la red (probado con la tablet el 24-11). |
| Tiempo real | Sin WebSocket: la página consulta cada 300 ms (antes 1 s, se bajó para ver el ángulo del sensor). |

## 2. Arquitectura

```text
Navegador (celular o PC)
  GET  /api/estado cada 300 ms
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
esp32/        main.py (firmware: lo único que se carga en la placa)
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
| `PIN_EXTENDER`, `PIN_RETRAER` | 13, 27 | Piernas: RPWM y LPWM del BTS7960 (placa propia; antes 26 y 27) |
| `PIN_HABILITAR` | `None` | R_EN y L_EN van a 3.3 V. Con un GPIO, se apaga al parar. |
| `PIERNAS_FINAL_ARRIBA`, `PIERNAS_FINAL_ABAJO` | 17, 16 | Finales de carrera de piernas (al extender y al retraer), contacto NC a GND con la resistencia interna. `None` si no están conectados: sin conectar se leen como tocados y piernas no se mueve. El código del compañero (`compi.txt`, no se sube) usaba 32 y 33, pero 33 es DIR de la altura. |
| `FINAL_ACTIVO` | 1 | Lo que lee el pin con el final tocado: 1 = NC (cable cortado también para), 0 = NO |
| `CABEZA_EXTENDER`, `CABEZA_RETRAER` | 22, 23 | Cabeza: RPWM y LPWM del BTS7960 (J6), o IN1 e IN2 del L298N con ENA en su jumper (placa v2; antes 18 y 19) |
| `VELOCIDAD`, `FRECUENCIA_PWM` | 100 %, 1000 Hz | Puentes H: siempre a toda potencia |
| `ALTURA_STEPPER` | `True` | Crea la sección `altura` |
| `ALTURA_STEP`, `ALTURA_DIR`, `ALTURA_EN` | 25, 33, 26 | DRV8825: STP, DIR y EN (EN activo en bajo; antes 13) |
| `SUBIR_CON_DIR` | 1 | Si "Subir" baja, se pone 0 |
| `PASOS_INICIO`, `PASOS_ACELERACION`, `PASOS_VELOCIDAD` | 250, 1500, 1000 | Arranca a 250 pasos/s y llega a 1000 en 0.5 s (5 vueltas/s en paso completo). A 1000 de golpe un NEMA 17 zumba y no arranca. Si zumba o se atora con carga: 800 o 600. |
| `MANTENER_FUERZA` | `True` | Quieto, el stepper sigue sujetando (EN siempre en 0) y se calienta |
| `ALTURA_LENTO_PASOS` | 400 | A menos de estos pasos de un tope la altura frena a `PASOS_INICIO` (frenar desde 1000 toma unos 310 pasos) |
| `ARCHIVO_ALTURA` | `altura.json` | Pasos, centro, topes y modo de la altura, en la memoria del ESP32; cargar `main.py` no lo borra |
| `PIERNAS_MPU`, `CABEZA_MPU` | `0x68`, `None` | Dirección del MPU6050 de cada sección (`None` = sin sensor). Los dos con AD0 a GND, porque cada uno va en su bus: cabeza será `0x68` al conectarse (con AD0 a VCC, `0x69`). |
| `PIERNAS_SCL`, `PIERNAS_SDA`, `PIERNAS_I2C_HZ` | 21, 19, 50000 | I2C 0, solo para el MPU de piernas (J7). Si falla con el cable puesto, 20000. |
| `CABEZA_SCL`, `CABEZA_SDA`, `CABEZA_I2C_HZ` | 5, 18, 20000 | I2C 1, solo para el MPU de cabeza (J8). Más lento por el cable de unos 2 m. |
| `MPU_CADA_MS`, `MPU_SUAVIZADO` | 100, 0.3 | Se lee cada MPU cada 100 ms y se suaviza (además del filtro de 5 Hz del chip) |
| `CALIBRACION_MINIMA` | 15 | Grados que "subido" tiene que quedar lejos de "plano" |
| `ARCHIVO_CALIBRACION` | `calibracion.json` | En la memoria del ESP32; cargar `main.py` no lo borra |
| `ACTIVO_BAJO` | `True` | Solo para los relés |
| `PAUSA_CAMBIO_MS` | 300 | Pausa entre apagar una sección y volver a arrancarla o invertirla |
| `LIMITE_SIN_ORDEN_MS` | 500 | Sin `M` en ese tiempo, la sección para sola |
| `WATCHDOG_MS` | 2000 | Watchdog, activado con la primera línea válida (así Thonny puede entrar antes) |
| `LARGO_MAXIMO` | 64 | Una línea más larga se descarta |

**Clases:**

- `PuenteH(pin_a, pin_b, pin_habilitar=None)`: un canal de L298N o un BTS7960. `"a"` extiende y `"b"` retrae; nunca los dos a la vez. Las salidas se crean en 0 (`salida_pwm`), porque algunas versiones arrancan el PWM a medias.
- `Stepper(step, dir, en)`: el PWM en STEP da un pulso por paso y su frecuencia es la velocidad. `"a"` sube. `actualizar()` hace la rampa y solo cambia la frecuencia cada 10 pasos/s. `poner_velocidad` suma 1 si la frecuencia sería 1000 Hz, para no compartir reloj con los puentes H.
- `ParReles(pin_a, pin_b)`: dos relés por actuador, del código del compañero. Solo con `MODULO = "reles"` (26/27 y 25/33).
- `Seccion(pares, finales=None)`: los actuadores de una sección arrancan, paran e invierten juntos. Lleva `marcha` (lo que está encendido), `pedido` (lo que pide la Raspberry), `visto` (último `M`) y `libre_desde` (fin de la pausa). `finales` es `{"a": pin, "b": pin}` (creados con `entrada_final`, pull-up interno); `en_final(cual)` y `topes()` los leen.

**Secciones creadas hoy:** `piernas` = `PuenteH(13, 27)` con finales 17 y 16, `cabeza` = `PuenteH(22, 23)` y `altura` = `Stepper(25, 33, 26)` (pines de la placa propia desde el 26-11). Si el stepper falla al crearse, imprime `# altura desactivada: ...` y las otras dos siguen. Para agregar una sección se edita `SECCIONES`: el servidor la detecta sola por las líneas `E`.

**Protocolo por USB.** Una orden por línea, terminada en `*XX` (XOR de los caracteres, en hexadecimal):

```text
Raspberry -> ESP32   M <seccion> 1    extender o subir; se repite cada 200 ms
                     M <seccion> -1   retraer o bajar
                     S <seccion>      detener esa sección (el servidor no la usa)
                     X                detener todo
                     P                sigo aquí (cuando no hay movimiento)
                     C <seccion> plano|subido   calibrar su MPU (solo con la sección quieta)
                     T altura centro|arriba|abajo|borrar   pasos de la altura (quieta y en automático)
                     A altura manual|auto   modo de la altura (manual = pedal)
ESP32 -> Raspberry   E altura=detenido cabeza=extendiendo piernas=contrayendo final_piernas=no ang_piernas=12.5*XX
                     # finales de piernas: no | # sensor de piernas: 12.5 | # camilla lista | # altura desactivada: ... | # error: ...
```

- Responde `E` a toda línea con comprobación correcta, aunque la orden no sea válida. Las líneas con comprobación mala se ignoran (si era un `M`, la sección para sola a los 500 ms).
- El LED azul (GPIO 2) está encendido mientras alguna sección está en marcha.
- Ctrl+C (Thonny) detiene todo y, si el watchdog ya estaba activo, reinicia la placa para que Thonny pueda entrar. Cualquier otro error detiene todo, imprime `# error: ...` y reinicia.

**Finales de carrera de piernas:** con el final de una dirección tocado, `Seccion.atender` apaga el puente H y no arranca hacia ese lado; hacia el otro sí. El pedido sigue: si fue ruido, arranca otra vez tras la pausa. La línea `E` agrega `final_piernas=no|arriba|abajo|falla` (falla = los dos a la vez, cable suelto) y al arrancar imprime `# finales de piernas: ...`. El servidor ignora ese dato por ahora (la página no lo muestra).

**Sensores de ángulo (MPU6050, rama `mpu-angulos`):** clase `Inclinometro`, uno por sección, cada uno en su propio I2C (el ESP32 tiene dos) con su velocidad: si falla el cable de uno, el otro sigue leyendo. Probado en simulación (27 pruebas, 26-11).

- **Cálculo:** cada 100 ms lee la gravedad (x, y, z) y la suaviza. Con "plano" y "subido" guardados, el eje de la bisagra es su producto cruz, y el ángulo es el giro de la gravedad actual desde "plano" alrededor de ese eje: positivo hacia "subido". Así no importa cómo quedó montado el módulo (probado en simulación con 4 montajes, incluido uno torcido: error de 0.2° o menos).
- **Línea `E`:** `ang_piernas=` el ángulo con un decimal, o `falla` (no responde), `sincal` (sin calibrar), `plano` (falta "subido") o `poco` ("subido" quedó a menos de 15° de "plano").
- **`C piernas plano`** guarda la lectura actual como plano y borra "subido". **`C piernas subido`** la guarda como subido si está a 15° o más; si no, queda en `poco`. Con la sección en marcha, `C` se ignora.
- **Falla:** tras 3 lecturas fallidas dice `falla` y reintenta cada 1 s. Si el módulo vuelve dormido (lee 0, 0, 0), lo despierta. Un MPU que falla nunca detiene los motores.
- **No los usa para parar:** el ángulo solo se informa. Parar en 45° o "Ir a" con motores es el paso siguiente.

**Pasos de la altura (rama `mpu-angulos`, 26-11, probado en simulación):** el `Stepper` cuenta los pasos que da (velocidad × tiempo, con `ticks_us`; + hacia arriba, 0 = centro). No hay sensor: si el motor se atasca y pierde pasos, la cuenta no se entera.

- **Línea `E`:** `pasos_altura=120 centro_altura=si|no topes_altura=-4000:3800|-:3800|no modo_altura=auto|manual`.
- **Centro y topes:** `T altura centro` pone la cuenta en 0 y la da por buena. `T altura arriba` y `abajo` guardan el tope donde está (arriba solo con pasos ≥ 1, abajo con ≤ −1, y con centro). `T altura borrar` quita los dos. Solo con la altura quieta y en automático.
- **Con centro y un tope:** frena a `PASOS_INICIO` a menos de `ALTURA_LENTO_PASOS` y se detiene en el tope (`Seccion.en_final` le pregunta al stepper, igual que a un final de carrera). Sin centro pero con topes, va siempre despacio.
- **Memoria:** guarda `altura.json` al parar, y al arrancar marca que se mueve. Si se reinicia o se corta la luz en marcha, al volver queda sin centro.
- **Manual (`A altura manual`):** para la altura, suelta el NEMA (EN = 1) y no obedece `M altura`. Como el pedal la mueve por fuera, la cuenta deja de valer: al volver a automático (EN = 0) queda sin centro. El modo se guarda y sigue tras reiniciar.
- La rampa ahora también frena; cambia la frecuencia de a 25 pasos/s.

**No hace:** leer finales de la cabeza (previstos en 4 y 32), medir corriente, limitar el tiempo de marcha ni parar por ángulo. La altura no lleva finales de carrera (decisión del 24-11). Los estados y `final_piernas` de la línea `E` llegan al servidor, pero el servidor solo usa los nombres de las secciones.

**Solo `main.py`:** `prueba_stepper.py` (prueba del stepper desde Thonny, con finales opcionales en GPIO 4 y 35) se borró el 24-11; sigue en git (`git show e1f6a15:esp32/prueba_stepper.py`). La conexión completa del DRV8825 quedó en el encabezado de `main.py`. Todo se prueba desde la página.

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
| `IP_CON_SESION` | 60 min | Portal: una IP con sesión usada en este tiempo recibe "sí hay internet" (dura lo mismo que el reparto de IP) |

**Estado (`Camilla`, en memoria):** `sesiones` (token → perfil), `titular`, `solicitud`, `respuestas`, `paro`, `motor` (una sección a la vez) y `hardware`. Reiniciar el servidor borra todo esto: saca a todos y libera el paro.

**Reglas:**

- **Sesión:** un perfil, una sesión. Entrar desde otro dispositivo cierra la anterior, y el control no pasa al nuevo.
- **Control:** un solo titular. Libre: lo toma quien entra (la página lo pide sola). Ocupado: solo lectura, y se puede pedir. El titular acepta o rechaza; si libera con un pedido pendiente, el control pasa a quien lo pidió. Cambiar de titular para el motor.
- **Paro:** cualquiera lo activa o lo libera, incluso sin sesión. Activarlo para el motor y bloquea `mover` y `paso`.
- **`vigilar()`** cada 0.5 s: hombre muerto, ESP32 perdido con motor en marcha, titular sin contacto 10 s, pedido vencido a los 35 s y sesiones de más de 12 h.

**Rutas:**

| Ruta | Sesión | Qué hace |
|---|---|---|
| `GET /api/estado` | Opcional (`X-Sesion`) | `usuario`, `nombre`, `rol`, `control {titular, usuario}`, `paro`, `simulacion`, `hardware {conectado, secciones, sensores {piernas: {angulo, estado}}, altura {pasos, centro, topes {abajo, arriba}, modo} o null}`, `solicitud` (solo al titular), `respuesta` (solo a quien pidió, una vez) y `telemetria {piernas: 12.5, altura: 37.8}` (secciones con sensor calibrado; la altura de 0 a 100 entre los topes, solo con centro, los dos topes y en automático) |
| `GET /` y archivos | No | La página compuesta; de `publico/` solo `.css`, `.js` y `.woff2` |
| `POST /api/login`, `/api/registro` | No | Abre una sesión. El registro crea un fisioterapeuta. `recordar: true` en el login devuelve además una `llave` para el equipo. Un login sin `recordar` anula las llaves de otros equipos del perfil. |
| `POST /api/reanudar {llave}` | No | Equipo recordado: abre sesión sin contraseña. Vale 30 días desde el último uso. La anulan entrar desde otro equipo, "Salir", una contraseña nueva, desactivar o borrar el perfil. |
| `POST /api/paro {activo}` | No | `activo: true` lo activa; cualquier otra cosa lo libera, también `{}` |
| `POST /api/logout` | Sí | Cierra la sesión y libera el control si lo tenía |
| `POST /api/control/tomar`, `solicitar`, `cancelar`, `responder {id, aceptar}`, `liberar` | Sí | Control |
| `POST /api/mover {seccion, dir, n}`, `/api/detener {seccion, n}` | Sí | Motor continuo. `dir` es 1 o −1. Un `detener` nunca se descarta. |
| `POST /api/altura {accion}` | Sí, desarrollador | `centro`, `arriba`, `abajo`, `borrar` (pasos del NEMA) o `manual`, `auto` (modo). Rechaza con la altura en marcha (salvo manual, que la para), los topes sin centro o en manual, el de arriba bajo el centro y el de abajo sobre él. Se anota en el registro. |
| `POST /api/calibrar {seccion, posicion}` | Sí, desarrollador | `plano` o `subido` para el MPU de cabeza o piernas. Rechaza si la sección se mueve o si el sensor está en `falla`. Se anota en el registro. (`/api/paso` se quitó: ninguna sección lo usaba.) |
| `POST /api/depuracion` | Sí, desarrollador | Modo, puerto del ESP32 y hace cuánto respondió, última orden enviada y última línea `E` recibida, sensores, motor, paro, titular, sesiones (usuario, rol, IP) y las últimas 60 líneas del registro del servidor. Otro rol: 403. |
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
  - Ya con sesión: la prueba de internet (`PRUEBAS_INTERNET`: Android `/generate_204` y `/gen_204`, Apple `/hotspot-detect.html`) recibe "sí hay internet" si viene de la IP de una sesión usada en los últimos 60 min (`tiene_sesion`). Así el equipo se queda en la red Camilla y no salta a otra red guardada ni a sus datos, y la tablet no muestra "sin internet". Costo: mientras tanto ese celular no tiene internet (WhatsApp, etc.). Al cerrar sesión o tras 60 min sin usarla vuelve a ser portal. Huawei "Wi-Fi+" y Samsung "Cambiar a datos móviles" cambian de red por su cuenta: se apagan en el celular. La tablet Huawei (Android 7) ignora `captive_portal_mode` por `adb`.
- **Login:** PBKDF2 fuera del candado; con contraseña incorrecta espera 1 s. Perfil desactivado: no entra.
- **Registro del sistema:** `anotar()` escribe a stderr con la hora (`journalctl -t python3` con el arranque automático). No anota las rutas de `SILENCIO` ni datos de pacientes, solo su número. `encender_red.sh` filtra estas frases: `inicio sesion`, `cerro sesion`, `creo su perfil`, `control: `, `el control a `, `PARO` y `contrasena incorrecta`.

### `web/paginas.py`

Compone `plantillas/index.html` resolviendo cada `<!-- incluir: ruta -->` en cada visita (al editar basta con recargar) y entrega solo `.css`, `.js` y `.woff2` de `publico/`. `camilla.db` y el código quedan fuera.

## 5. Base de datos: `web/basedatos.py`

- `web/camilla.db`, creada con permiso 600. Está en `.gitignore` porque tiene datos de pacientes y el repositorio es público.
- **`usuarios`:** `id`, `usuario` (único, sin distinguir mayúsculas), `nombre`, `rol` (`admin` o `fisio`), `activo`, `dev` (0 o 1; columna agregada el 26-11 con `ALTER TABLE` en `iniciar()`), `sal`, `clave` (PBKDF2-HMAC-SHA256, 300 000 vueltas, sal de 16 bytes) y `creado`.
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
| `main.js`, `utilidades.js` | Arranque (conecta los módulos) y ayudas (`porId`, `bajarArchivo`...) |
| `api/cliente.js`, `sondeo.js`, `ordenes.js`, `admin.js` | Peticiones, consulta cada 300 ms, órdenes y pedidos de administración |
| `vistas/calibrar.js` | Panel "Calibrar" de cabeza y piernas (solo desarrollador), dentro de la tarjeta porque entre plano y subido hay que mover la sección |
| `vistas/altura.js` | Altura: selector Automático / Manual (pedal) y panel "Pasos" (centro, topes y pasos en vivo), solo desarrollador. "Borrar topes" se toca dos veces. |
| `camilla/movimiento.js` | Botón sostenido, estimación, "Ir a" y paro |
| `camilla/mandos.js` | Eventos de los botones, Esc, Plano y Bloquear |
| `camilla/telemetria.js` | `aplicarAngulos` y la API `window.camilla` |
| `ui/pintado.js`, `ui/dibujo.js` | Pantalla y dibujo SVG; nunca mandan órdenes |
| `ui/modales.js`, `avisos.js`, `formularios.js`, `registro.js` | Modales, toasts, ayudas de formularios y "Registro de comandos (desarrollo)" |
| `vistas/depuracion.js` | Panel "Depuración (desarrollador)": pregunta `/api/depuracion` cada 1 s mientras está abierto |
| `vistas/acceso.js`, `sesion.js`, `cesion.js`, `pestanas.js`, `pacientes.js`, `usuarios.js` | Login y registro, entrar y salir, pasar el control, pestañas por rol, pacientes y perfiles |
| `vistas/manuales.js`, `pin.js`, `pantalla.js` | Botón "Manuales", PIN de Registros y pantalla completa de la tablet |

**`config.js` hoy:**

| Sección | Escala | Paso cada 70 ms | Opciones |
|---|---|---|---|
| `altura` | 0 a 100, sin número en pantalla | 2 | `continua`, `sinTope`, `numerica: false` |
| `cabeza` | −30° a 70° | 1° | `continua`, `sinTope` |
| `piernas` | 0° a 45° | 1° | `continua`, `sinTope` |

- `continua`: el motor corre mientras se mantiene el botón (`/api/mover`). Hoy todas las secciones son `continua`.
- **Con sensor calibrado** (`conSensor` en `estado.js`): el número es el ángulo real que llega en `telemetria`, también mientras se mueve; la página no estima. "Ir a" se deshabilita y "Plano 0°" salta esa sección, porque todavía no mueven motores. Cada tarjeta dice de dónde sale el ángulo: Estimado, Sensor, Sin calibrar, Falta subido, Calibrar de nuevo o Falla del sensor.
- `sinTope`: la estimación nunca corta el movimiento ni deshabilita el botón al llegar al límite. El motor sigue hasta que se suelta o hasta el tope interno del actuador.
- Tiempos: `CONSULTA_MS` 300, `FALLOS_PARA_CAIDA` 3, `MANTENER_MS` 400, `ESPERA_SOLICITUD` 30 y `ESPERA_RESPUESTA` 30. Plazos de las peticiones: 2.5 s para el estado, 8 s para login y registro, 5 s para lo demás.

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
- **Desarrollador (rama `mpu-angulos`, 26-11):** es un administrador con `dev = 1`; el servidor y la página lo ven como rol `dev`.
  - Puede todo lo del admin (`basedatos.ADMINS` y `esAdmin()` en `config.js`).
  - Es el **único que calibra** los sensores de ángulo y el único que ve, al fondo de Control, "Depuración (desarrollador)" y "Registro de comandos (desarrollo)"; los demás ya no ven el registro.
  - **Solo se da por terminal:** `python3 web/basedatos.py desarrollador USUARIO`. `admin USUARIO` lo deja como administrador normal. Desde Usuarios no se puede dar ni quitar, y su rol no se puede cambiar ("solo desde la terminal").
- **Pedido de control:** quien pide ve 30 s de espera; el titular tiene 30 s para decidir y, si no responde, se rechaza solo.
- **Pantalla completa (`vistas/pantalla.js`):** en un equipo táctil recordado, cada toque (`click`, no `pointerdown`) pide pantalla completa si no la tiene: oculta la barra de Android y la de Chrome. Android la quita al apagarse la pantalla y vuelve con el siguiente toque. La laptop no cambia.
- `window.camilla` expone `aplicarAngulos`, `estado`, `irA` y `paro` para probar desde la consola del navegador. `topeAltura` y el aviso "En el tope ..." de la altura se quitaron el 24-11: la altura no tiene finales.

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

**Fuente de motores:** S-480-12, 12 V y 40 A.

- **Regleta de 9 tornillos:** L, N y ⏚ (120 V), 3 × −V y 3 × +V, y el potenciómetro V.ADJ (dejarlo en 12.0 V).
- **Cableado en estrella:** cada equipo lleva su propio par +V/−V, con su fusible en el +V. Cabeza 7 A, Piernas 10 A y J4 de la placa (DRV8825) 3 A. Los tres ya se consiguieron (26-11).
- **BTS7960:** los 12 V van directo de la fuente a B+/B−; nunca pasan por la placa.
- **Consumo:** con todo moviéndose pide unos 15 A.

**Placa propia del ESP32 (25-11; versión 2 el 26-11; sin fresar).** Una cara de cobre, 106 × 70 mm, para la fresadora CNC. La versión 2 rehízo solo el lado derecho para que cada MPU tenga su propio I2C: J6 subió a la orilla derecha, J7 y J8 bajaron y el motor de cabeza pasó al 22 y 23. Revisada con la DRC del generador y con una revisión aparte sobre los archivos que se fresan: sin cortos ni cortes, 0.8 mm mínimo entre señales.

- **Archivos:** en el escritorio del usuario, carpeta `placa-camilla/`, con `LEEME.txt`. Ya están en espejo. La versión 1 quedó en `placa-camilla/version-anterior-bus-compartido/`: no se fresa. La guía está en la sección 14.
- **Montaje:** el ESP32 DOIT de 30 pines y el DRV8825 van enchufados en tiras hembra; los módulos, con cables Dupont, y los MPU con cable de red (más abajo).

| Conector | Qué va | Pines |
|---|---|---|
| J2 | DRV8825 de la altura | DIR 33, STP 25 y EN 26. SLP y RST a 3V3; M0 a M2 sin conectar (paso completo). |
| J3 | NEMA 17 (tira macho de 4) | 2A, 1A, 1B y 2B |
| J4 | 12 V del DRV8825 (bornera) | +12 V y GND, con fusible de 3 A. C1 (100 a 1000 µF, 25 V) en VMOT, con el + abajo. |
| J5 | BTS7960 de piernas | RPWM 13 y LPWM 27. R_EN, L_EN y VCC a 3V3; R_IS y L_IS sin conectar. |
| J6 | BTS7960 de cabeza (orilla derecha) | RPWM 22 y LPWM 23 (antes 18 y 19); lo demás como J5 |
| J7, J8 | MPU6050 de piernas y de cabeza | De arriba hacia abajo VCC (3V3), GND, SCL y SDA. Cada uno con su I2C: J7 SCL 21 y SDA 19; J8 SCL 5 y SDA 18. Los dos con AD0 a GND (0x68). |
| J9 | Finales de carrera | Cabeza abajo 32, cabeza arriba 4, piernas abajo 16 y piernas arriba 17, cada uno con un GND al lado. |
| JP1 | Puente de alambre | Unos 13 mm entre J7 y J8, hacia abajo. Une el GND de los MPU con el resto. |

**Pines que cambian con la placa** (comparado con la protoboard). Se cambiaron para que las pistas no se crucen en una sola cara.

| Pin | Antes | Con la placa | En `main.py` |
|---|---|---|---|
| GPIO 26 | Piernas extender (RPWM) | Altura EN | `ALTURA_EN = 26` (hecho el 26-11) |
| GPIO 13 | Altura EN | Piernas extender (RPWM) | `PIN_EXTENDER = 13` (hecho el 26-11) |
| GPIO 4 | Libre (se pensaba en 23) | Final de cabeza arriba | Falta el código de los finales de cabeza |
| GPIO 22 | SCL de los dos MPU | Cabeza extender (RPWM) | `CABEZA_EXTENDER = 22` |
| GPIO 23 | Libre | Cabeza retraer (LPWM) | `CABEZA_RETRAER = 23` |
| GPIO 21 | SDA de los dos MPU | SCL del MPU de piernas | `PIERNAS_SCL = 21` |
| GPIO 19 | Cabeza retraer | SDA del MPU de piernas | `PIERNAS_SDA = 19` |
| GPIO 18 | Cabeza extender | SDA del MPU de cabeza | `CABEZA_SDA = 18` |
| GPIO 5 | Libre | SCL del MPU de cabeza | `CABEZA_SCL = 5` |

- **Siguen igual:** 25 y 33 (altura), 27 (piernas retraer), 17 y 16 (finales de piernas), 32 (final de cabeza abajo) y 2 (LED).
- **El 5 va en el I2C y no en un motor:** al arrancar, el ESP32 saca pulsos por ese pin. En un motor serían un tirón; en el I2C no hacen nada, y la pull-up lo deja en alto, como lo necesita para arrancar.
- **Placa y `main.py` tienen que coincidir.** Desde el 26-11, `main.py` de `mpu-angulos` usa los pines de la placa v2 (en `desarrollo-final` la cabeza sigue en 18 y 19 y no hay código de los MPU).
  - Si se sigue usando la protoboard vieja, pasar el cable RPWM de piernas del 26 al 13, el EN del DRV8825 del 13 al 26 y la cabeza del 18 y 19 al 22 y 23.
  - Si no coinciden, Piernas no extiende y "extender piernas" prende y apaga el driver de la altura. Con `MANTENER_FUERZA = False` sería peor: Piernas extendería sola, sin que sus finales la paren.

**Cable a cada MPU (26-11):** Cat5e multifilar (de patch cord), 100 % cobre (no CCA); FTP si lo hay, con la lámina a GND solo del lado de la placa. Uno por MPU, el recorrido + 30 cm (cabeza, unos 2 m).

| Hilo | Pin (J7/J8 y GY-521) |
|---|---|
| Azul | VCC (3.3 V) |
| Naranja | SCL |
| Verde | SDA |
| Blanco/azul, blanco/naranja y blanco/verde | GND, los tres juntos en las dos puntas |
| Marrón y blanco/marrón | Sin usar: cortados y aislados (repuesto) |

- Cada señal va trenzada con un GND. SCL y SDA nunca en el mismo par.
- Punta de la placa: tira macho de 4 soldada al cable, en el orden VCC, GND, SCL y SDA. Punta del módulo: soldado al GY-521, con el puente de AD0 a GND.
- Lejos de los cables de los motores (si se cruzan, en ángulo recto), con una vuelta suelta en la bisagra.

**Conexiones conocidas al 16-11, en protoboard** (antes de la placa propia; confirmar con el usuario si cambió algo):

- **Piernas en el MD-BTS7960:** RPWM a GPIO 26, LPWM a GPIO 27, R_EN y L_EN a 3.3 V, VCC a 3V3 y GND al GND del ESP32. Los 2 actuadores en paralelo: M+ a sus cables A y M− a sus cables B. R_IS y L_IS sin conectar (pueden pasar de 3.3 V). En estas placas el GND de control y B− suelen estar unidos: comprobarlo con el multímetro.
- **Cabeza en el L298N** (provisional, aguanta unos 2 A por canal): IN1 a GPIO 18, IN2 a GPIO 19, jumper de ENA puesto, OUT1 y OUT2 al actuador. 12 V con fusible de 3 A; GND a V− y al GND del ESP32; el 5V sin conectar, con el jumper del regulador puesto. Revisar que traiga sus 8 diodos y tocar el disipador al probar.
- **Altura en el DRV8825** (placa morada con disipador; los pines tienen nombres de clon: STP, 1A/2A/1B/2B): STP a GPIO 25, DIR a 33, EN a 13, RST y SLP puenteados a 3.3 V. Fuente de 12 V solo a VMOT/GND, con un capacitor en VMOT (100 µF o más; en la guía se usó 1000 µF). Motor en 1A/2A y 1B/2B. Corriente = Vref × 2. Nunca conectar o desconectar el motor con la fuente encendida.
  - En la protoboard del usuario (disipador arriba, filas 18 a 25): a la izquierda GND, FLT, 2A, 1A, 1B, 2B, GND y VMOT; a la derecha DIR, STP, SLP, RST, M2, M1, M0 y EN.
  - El 24-11 el usuario cargó `main.py` y movió la altura desde la página. Sin finales de carrera.

**Finales de carrera** (microswitch de 3 patas C, NO y NC; se usa **C a GND y NC al GPIO**, así un cable cortado también para):

- Piernas: 17 arriba (al extender) y 16 abajo (al retraer), en `main.py`. Montados por el compañero; falta pasarlos a esos pines y probarlos.
- Cabeza: 4 arriba y 32 abajo (los de la placa; antes se pensaba en 23 para arriba), sin código. Falta confirmar que en la cabeza extender = subir.
- Altura: no lleva (decisión del 24-11).
- El código del compañero (`compi.txt`, por WiFi) los tenía en 32 y 33; 33 es DIR de la altura.

**Sensor de ángulo de piernas (24-11; MPU6050 elegido y probado en la mesa el 26-11):** la bisagra es un tubo hueco de 16.5 mm por fuera y 13.7 mm por dentro, que gira con las piernas. Los cojines se juntan justo encima y la sección termina al ras del extremo del tubo. El módulo AS5600 (23 × 23 mm, imán de 3.5 mm) no cabe: rozaría con la sección al bajarla o quedaría salido para patearlo.

- Elegido: **MPU6050 (GY-521)** debajo de la sección de piernas (cualquier parte que gire con ella), con su propio I2C (con la placa v2: SCL 21 y SDA 19). Mide contra la gravedad y no se gasta.
  - **Prueba del 26-11:** primer GY-521 en la mesa, desde la PC por COM4, con SCL 22 y SDA 21 (antes de la placa v2). Dio `[104]` y WHO_AM_I `0x68` (original), con 40 lecturas sin error que siguen la inclinación. La gravedad mide entre 15 200 y 16 100 (1 g = 16 384).
  - **Montaje:** parado, atornillado a un soporte impreso que cuelga de la sección de piernas (tubo negro que sube con los actuadores). Con X vertical, la bisagra queda paralela a Y o a Z según cómo se gire el soporte.
  - **Calibración:** dos posiciones desde la página (plano y subido unos 30°), solo el perfil Desarrollador. El ESP32 calcula el eje de la bisagra y guarda la calibración en `calibracion.json`. Código en la rama `mpu-angulos` (sección 3), sin probar en la camilla.
- Si tiene que ir en la bisagra: **potenciómetro RV09** (9 mm) con su eje en un tapón impreso dentro del tubo y el cuerpo fijo al asiento. Dura unos 10 000 a 15 000 ciclos; uno de plástico conductivo (Bourns 3382 o similar) dura mucho más. Va a 34, 36 o 39.

**Definitivo (aprobado):** un MD-BTS7960 (43 A, 5.5 a 25 V) por sección, con los dos actuadores en paralelo.

- Fusible retardado, uno por módulo, en B+, de vidrio de 6 × 30 mm, con portafusible en línea de 15 A o más. Si se funde, paran los dos actuadores juntos.
  - **Cabeza: 7 A.** Se planeó 7.5 A, pero solo se consiguió de 7 A (26-11). Sirve porque los 2 actuadores piden como máximo 6 A. Comprobar que sea retardado (marca T). Si es rápido y se funde al arrancar sin nada trabado, cambiarlo por uno retardado.
  - **Piernas: 10 A.** No usar 7 A: los 2 actuadores piden unos 8 A.
- Cable de 14 AWG para B+ y B−, y de 16 AWG a los actuadores.
- Sin TVS al principio: no hay contactos que chispeen y el módulo trae diodos internos.
- Si EN va a un GPIO, resistencia de 10 kΩ de EN a GND, para que quede apagado mientras arranca el ESP32.
- El BTS7960 de Cabeza va en J6: RPWM 22 y LPWM 23 (placa v2; antes se pensaba en 18 y 19).

**Relés (solo historia):** el módulo de 4 relés SPDT se usó el 09-11. El firmware conserva `MODULO = "reles"` (cabeza con 26/27 y 25/33, activo en bajo). No sirve a la vez que los puentes, porque comparte pines.

**Pines del ESP32** (los de la placa propia, y los de `main.py` desde el 26-11):

| Uso | GPIO |
|---|---|
| Ocupados | 13 y 27 (piernas); 22 y 23 (cabeza); 25, 33 y 26 (altura: STEP, DIR y EN); 17 y 16 (finales de piernas); 4 y 32 (finales de cabeza); 21 SCL y 19 SDA (MPU de piernas, I2C 0); 5 SCL y 18 SDA (MPU de cabeza, I2C 1); 2 (LED); 1 y 3 (USB con la Raspberry) |
| Reservados | 34, 36 o 39: potenciómetro, si se usa |
| Libres | 14 (da pulsos al arrancar), 35, y los de 34/36/39 que no se usen. Del 34 al 39 son solo de entrada y no tienen resistencia interna (un final ahí necesita 10 kΩ a 3.3 V). En la WROVER, 16 y 17 no están libres: la placa es WROOM. |
| No usar | 6 a 11 (memoria). Evitar 0, 12 y 15, que son de arranque. El 5 también lo es, pero en el I2C de cabeza no molesta. |

**Fusibles conseguidos (26-11):** 7 A (cabeza), 10 A (piernas) y 3 A (J4 de la placa), de vidrio.

**Lista de compra pendiente:** 2 portafusibles en línea de 15 A o más, más uno para el fusible de J4, 2 resistencias de 10 kΩ, 2 BTS7960, cable de 14 y 16 AWG, y para los MPU cable Cat5e multifilar de cobre (uno por MPU), 2 tiras macho de 4 y termoencogible. De la tienda **no sirven**: TVS de 3.3, 5, 9 o 12 V (conducen a 12 V y queman el fusible), SMBJ170CA y 1.5KE200CA (no actúan), SM12C (es para datos), ni un 1N4007 entre los cables del actuador (hace corto al invertir).

## 9. Problemas conocidos

**Seguridad** (comprobados en el código, sin resolver):

1. **No hay paro físico** que corte la fuente de los motores sin depender de ninguna placa. Sin eso no se debe probar con personas.
2. El paro se libera con un segundo toque: el botón alterna sin confirmar.
3. El paro se libera sin sesión, y `POST /api/paro {}` también lo apaga.
4. El paro vive en memoria: reiniciar el servidor (o que systemd lo reinicie) lo borra.
5. El hombre muerto del servidor para entre 1.0 y 1.5 s; el ESP32 para en 0.5 s si deja de recibir.
6. Con `sinTope` y sin sensores, nada impide que un actuador empuje contra la estructura si se mantiene el botón: solo lo frena su tope interno. Piernas ya tiene finales en el código (falta montarlos en 17 y 16); cabeza no, y la altura no los va a tener: el husillo sigue hasta su extremo.
7. No hay tiempo máximo de marcha por sección.

**Lo que la pantalla muestra y no es cierto:** grados sin sensor calibrado y barra de altura estimados; "Ir a" y "Plano 0°", que no mueven nada pero dicen "Ajustando a ..."; "Un toque = 1°" y `+1°`/`−1°`. Cada pantalla tiene su propia estimación.

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
- `GUIA.md` e `INTEGRACION.md` no incluyen `esp32/`, `hardware.py`, `--simulador`, `n`, `hardware` en `/api/estado`, `python3-serial`, la reapertura del puerto ni el stepper, siguen nombrando `SIMULACION` (ya no existe) y dicen "Un toque = 1°" y que no hay ESP32. Tampoco la tablet, el PIN, las descargas, el portal ni los finales de piernas.
- El manual técnico y el de usuario (rama `manuales` y sus guías publicadas) describen dos AS5600 y finales de carrera en la altura: ya no corresponde.

**Conservar:** entrega de archivos limitada a `publico/`, SQL parametrizado, roles validados en el servidor y la máquina de estados del control.

## 10. Lo que falta para terminar

**Decisiones del usuario:**

1. **Pantalla sin sensores:** seguir con grados estimados, pasar a SUBIENDO / BAJANDO / EN REPOSO, o poner sensores. En cualquier caso hay que decidir qué pasa con "Ir a", "Plano 0°" y los textos de 1°.
2. **Sensor de ángulo de piernas:** decidido el MPU6050 bajo la sección (sección 8); código en la rama `mpu-angulos`, falta probarlo en la camilla. El AS5600 no cabe en la bisagra. Historia: el 11-11 se pensó en un encoder óptico en código Gray (rama `backup-cambios-esp32`) y el 20-11 en dos AS5600 (rama `manuales`); análisis viejo en `git show 1eaf7a2:CONTEXTO.md`.
3. **Perfiles:** registro abierto o que los cree el administrador.
4. **Registro de uso:** solo cuentas y pacientes, o también un historial de quién movió la camilla y cuándo.
5. **Altura:** qué husillo lleva (mm por vuelta) y si el NEMA 17 aguanta la camilla con una persona. Como no lleva finales, el husillo tiene que aguantar llegar a su extremo, o hay que soltar a tiempo. Si no, NEMA 23 con reductor o actuador lineal con BTS7960. Si el husillo no es autobloqueante (paso largo, como T8×8), la camilla baja sola al cortar la energía: hace falta husillo de paso fino, freno o reductor.
6. Si se deja la sección 11 de `INTEGRACION.md` en un documento que se va a evaluar.
7. **Cabeza:** confirmar que extender = subir, para sus finales en 4 y 32.

**Software que se puede hacer ya:**

- Arreglo del paro (propuesta en la sección 13).
- Mostrar `final_piernas` en la página (hoy el servidor lo ignora): aviso "Piernas en el tope" y botón deshabilitado hacia ese lado.
- Finales de la cabeza en `main.py` (4 arriba y 32 abajo), igual que piernas, cuando se confirme la dirección.
- Tiempo máximo de marcha por sección en el ESP32, sobre todo en la altura, que no tiene finales.
- Corregir los manuales (AS5600 y finales de la altura ya no van).
- Textos de la pantalla que no corresponden.
- Bajar `HOMBRE_MUERTO` o revisar el servidor más seguido.
- Aceptar tildes, ñ y espacios en los nombres.
- Actualizar `GUIA.md` e `INTEGRACION.md`.
- Volver a armar las pruebas en simulación: los scripts del 09-11 al 11-11 (`falsos.py`, `probar_*.py`) se perdieron con las carpetas temporales. Conviene guardarlos en el repositorio.

**Hardware:**

- Placa propia, en este orden:
  1. Imprimir la plantilla 1:1 y comprobar el ESP32 y el DRV8825.
  2. Fresar.
  3. Revisar con el multímetro, sin piezas, que ninguna pista suene con su vecina y que 3V3 y VMOT no suenen con GND.
  4. Soldar.
  5. Cargar el `main.py` con los pines nuevos y encender por partes (guía en la sección 14).
- Pasar los finales de piernas a 17 y 16 (C a GND, NC al GPIO), cargar `main.py` y probar: al arrancar debe decir `# finales de piernas: no`.
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
python web/basedatos.py desarrollador USUARIO   # perfil Desarrollador: admin + depuración + calibrar (rama mpu-angulos)
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

**Cargar el ESP32 con Thonny** (también está en la Raspberry). En la PC del usuario, el controlador CP210x se instaló el 26-11 y el ESP32 aparece en COM4. En Thonny, el intérprete es "MicroPython (ESP32)":

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
- **Rama instalada: `desarrollo-final`** (`b7895e3`, portal, el 24-11). Antes tenía `muestra-citein`, la de la presentación del 13-11. Para volver a ella: `git checkout muestra-citein` y reiniciar `camilla-pagina`. Desde `e1f6a15` (finales de piernas), `esp32/main.py` ya no es igual entre las dos ramas; `red/` sí.
- **ESP32:** el 24-11 tenía el `main.py` de antes de los finales de piernas (respondió `# camilla lista`).
- **Tablet de control:** Huawei, Android 7, Chrome 101. Entra con el perfil del usuario (más adelante, el de la licenciada de fisioterapia) y "Recordar este equipo". IP 10.42.0.121 el 24-11. Se probó por `adb` con depuración USB (ya se puede apagar).
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
- Tablet fija de control (23-11): "Recordar este equipo", un perfil = una sesión, retoma el control al despertar solo si está libre, PIN de Registros con cierre a los 30 min, pantalla completa y app fijada en Android.
- Portal (24-11): sin sesión, tipo hotel; con sesión, "sí hay internet" para que el equipo no salte de red (opción B).
- Finales de piernas con contacto NC en 17 y 16 (24-11). La altura no lleva finales (24-11).
- Solo `main.py`: `prueba_stepper.py` se borró (24-11).
- AS5600 descartado en la bisagra de piernas: no cabe (24-11).

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
- Stepper de la altura (DRV8825, Vref, micropasos; sin finales y solo con `main.py` desde el 24-11): https://claude.ai/artifact/AW9F4AJEpPeUgS7757k2Cr
- Montaje del AS5600 (supone un perno con tuerca; la bisagra real es un tubo, así que no aplica): https://claude.ai/artifact/DwFKWLFjFtK2hQHj96AAH7
- Puente H de las piernas (BTS7960 con 2 actuadores): https://claude.ai/artifact/1vXRyzqTNfADsvsiMQrvpW
- Placa propia del ESP32, versión 2 (mapa de la placa, fuente de 12 V con simulador de corriente, guía de conexión paso a paso y cable de red a los MPU con cada color a su pin): https://claude.ai/artifact/6wx6oaaJUZ4oKGFcfhMcZv
- Imagen de los pines de la placa v2: `placa-camilla/cambios-pines.png`, en el escritorio del usuario.

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
- El ángulo real llega en `telemetria` y `aplicarAngulos` lo aplica siempre; `darPaso` no estima una sección con sensor. El estado de cada sensor viene aparte, en `hardware.sensores`, y no se compara con el resto de `hardware` (si no, el registro anotaría cada lectura).
- **Altura bloqueada** (`bloqueoAltura` en `estado.js`, `bloqueo_altura` en `servidor.py`): en manual nadie la mueve; con topes y sin centro solo el desarrollador (despacio). `puedeMover('altura')` lo revisa y el servidor rechaza `/api/mover`. Cambiar el modo, el centro o los topes es solo del desarrollador.
- Con centro y los dos topes, `conSensor('altura')` es verdadero: la barra de la altura muestra la posición real que manda el servidor en `telemetria.altura` y la página deja de estimarla.
- El Simulador también simula la altura: 800 pasos/s, con centro y topes −4000 / 4000 al arrancar.
- El Simulador (`--simulador`) también simula los sensores de cabeza y piernas, calibrados: 3°/s y 4°/s mientras se mueven, con su calibración.
- Las reglas de `basedatos.py`, `ui/formularios.js`, `vistas/acceso.js` y `vistas/pacientes.js` se cambian juntas. Los límites de cada sección ya solo están en `CONFIG` (`config.js`).
- `CONFIG.altura.numerica = true` rompe la página con un `TypeError`: la altura no tiene esos elementos en el HTML.
- Si se deshabilita un botón mientras se mantiene pulsado, puede no llegar el `pointerup`. Por eso existe `sinTope`.
- Una orden `detener` nunca se descarta, aunque su número sea viejo.
- Al abrir el puerto el ESP32 se reinicia: `ESPERA_ARRANQUE` (6 s) debe ser mayor que `SILENCIO_REABRIR` (3 s), o se queda reabriendo en bucle.
- `MODULO = "reles"` usa 25 y 33, los mismos de la altura: en ese modo no se crea la altura.
- Un final de carrera configurado en `main.py` y sin conectar se lee como tocado (NC con pull-up): piernas no se mueve. Para probar sin ellos, `PIERNAS_FINAL_ARRIBA = None` y `PIERNAS_FINAL_ABAJO = None`.
- `hardware.leer_respuesta` ignora lo que en la línea `E` no es una sección (`final_piernas`): se puede agregar datos sin romper el servidor.
- `encender_red.sh` filtra el texto de `anotar()` y la línea `"GET / `: cambiar esas frases rompe su monitor.
- `ESPERA_SOLICITUD` es 35 s en el servidor y 30 s en la página, a propósito.
- `solicitud.usuario` y `respuesta.usuario` traen el nombre para mostrar, no el usuario.
- Los métodos de `Camilla` asumen `candado` tomado; SQLite, PBKDF2 y el puerto serie van fuera.
