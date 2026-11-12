# Contexto del proyecto

**Fecha:** 09-11-2026, con agregados del 10-11 y del 11-11-2026. Resumen para retomar el trabajo desde cero: qué se busca, cómo está todo y qué sigue. El detalle del sistema está en `GUIA.md` e `INTEGRACION.md`, pero esas dos **todavía no incluyen la integración del ESP32** (ver "Documentación pendiente").

## Dónde quedamos

- **09-11: primera prueba real completa.** La cadena página → Raspberry → USB → ESP32 → módulo de relés → actuadores funcionó: se movieron. Al desconectar el USB, la página avisa "Sin conexión con los motores" y los relés se apagan. Al reconectarlo, vuelve solo.
- Con los motores en marcha aparecen **errores USB** (`urb stopped: -32`) que dejaban el puerto mudo hasta reiniciar el servidor. `web/hardware.py` ya reabre el puerto solo (commit `99a91cf`, en GitHub). **Falta bajarlo en la Raspberry y probarlo con motores.**
- El módulo de relés es **solo para la presentación del viernes 13-11-2026**. El definitivo es **un BTS7960 por sección** (ver "Hardware").
- **09-11, tarde:** el compañero actualizó su código para manejar un puente H (L298N o BTS7960) en los pines 25 y 26. `esp32/main.py` se adaptó: ahora usa `MODULO = "puente"` por omisión, y los relés quedan como opción. **Se cargó en la placa real y funcionó con el puente H en Cabeza**: subir, bajar y parar desde la página, sin cortes del ESP32 durante unos 3 minutos de prueba. Está en el commit `fa1a602`, en GitHub.
- **11-11: llegó el MD-BTS7960 y se decidió empezar por Piernas, no por Cabeza.** El compañero ya probó los 2 actuadores de Piernas en un solo BTS7960 y aguantó, con su código (WiFi y PWM; copia en `compi.txt`, que **tiene la clave del WiFi: no se sube**). Ese código usa **GPIO 26 → RPWM y GPIO 27 → LPWM**; su comentario dice 25 y 26, pero lo que funcionó fue 26 y 27. `esp32/main.py` ahora maneja `piernas` en el modo `puente` con esos pines, siempre al 100 %. `config.js` le puso `continua` y `sinTope` a Piernas. Subido en `1d4ed7d`, y Piernas **funcionó en la placa real** con el BTS7960.
- **11-11, después:** mientras llega otro BTS7960, Cabeza va en un **L298N** (el rojo) con **1 solo actuador**, porque falta que llegue el otro. Se usan los pines del nuevo código del compañero (`compi.txt`): **GPIO 18 → IN1 (extender) y GPIO 19 → IN2 (retraer)**, con ENA en su jumper. `esp32/main.py` ahora tiene las dos secciones en modo `puente` (`CABEZA_EXTENDER` y `CABEZA_RETRAER`). Probado en simulación sin fallas (`probar_dos_puentes.py` y `probar_panel_dos.py`). **Sin commit, por pedido del usuario**: no subir nada sin que lo pida explícitamente. Se lleva a la Raspberry cuando el usuario decida (git, Thonny o scp).
- **10-11: se habló de sensores de ángulo para Cabeza y Piernas.** Ver "Propuestas → Sensores de ángulo".
- **11-11: el usuario eligió un encoder óptico absoluto en código Gray para Piernas, de 0° a 90°**, con LED y fototransistores sueltos que arma él, e impreso en 3D por un compañero. El usuario lo movió a la **rama local `backup-cambios-esp32`** (commit `ce2474a`, carpeta `encoder/`). Ese commit también guarda `codigoesp32.txt` con la clave del WiFi: **no subir esa rama así**; para publicar el encoder, armar una rama sin ese archivo. Primero se arma un **banco de prueba** que se gira a mano. Guía visual: https://claude.ai/artifact/MAu8PJ5JfVQvSUGJZH4XQU. Ver "Encoder de piernas".
- Rama `esp32-conexion`, en GitHub en `fa1a602`. En el PC la rama sigue enlazada a `origin/optimizaciones-esp32`, así que hay que subir con `git push origin esp32-conexion`.

**Siguiente, en orden:**

1. **Bajar el código en la Raspberry** con `git pull` y **volver a cargar `esp32/main.py` en el ESP32 con Thonny** (Upload to /), porque cambió a `piernas` en 26 y 27. Comprobar en Thonny con `print("piernas" in open("main.py").read())`, que debe dar `True`. Al levantar el servidor debe salir `ESP32 conectado en /dev/ttyUSB0: piernas`. Probar subir, bajar y parar Piernas. Si sube cuando debería bajar, intercambiar `PIN_EXTENDER` y `PIN_RETRAER`. Si se corta, debe salir `se perdio la conexion con el ESP32: dejo de responder` y luego `ESP32 conectado`, sin reiniciar nada.
2. **Cabeza en el L298N (18 y 19), con 1 actuador:** llevar `main.py` a la placa y probar. El L298N aguanta unos 2 A por canal y el 3000N llega a 3 A: probarlo suelto, en tandas cortas y tocando el disipador. Después, un BTS7960 propio para Cabeza con sus 2 actuadores.
3. **Probar con la red Camilla** desde el celular (ver "Comandos"): la página no debe perder la conexión mientras se mueve el motor. Luego, hacer el conteo de errores USB. Al escribir esto, el usuario no había reportado el resultado.
4. **Detener los registros** que quedaron corriendo en la Raspberry (ver "Diagnóstico").
5. **Piernas con BTS7960:** firmware y página listos el 11-11. Se probaron con simulación: el firmware con PWM falso y el panel en Chrome contra el firmware falso. Falta la prueba en la Raspberry (paso 1).
6. **Para recargar el firmware:** con el servidor apagado, presionar EN y después Stop en Thonny (ver "Problemas").
7. **Encoder de piernas:** imprimir las 4 piezas, comprar los componentes y armar el banco siguiendo la guía. Después, con las medidas de la bisagra, diseñar los soportes para la camilla (ver "Encoder de piernas").

## Qué se busca y cómo está

Control remoto web en una Raspberry Pi 4 para la altura, la cabeza y las piernas de una camilla, para uso en un centro de salud. Debe funcionar sin intervención del desarrollador. El PC Windows es solo para desarrollar, porque la Pi es lenta. La red es local, de la propia Raspberry, sin internet.

| Objetivo | Estado |
|---|---|
| Control remoto web | Hecho. Cabeza probada con placa real y relés el 09-11. Piernas y altura salen como "Sin actuador". |
| Registro en SQLite | Hay `usuarios` y `pacientes`. No hay bitácora de uso. |
| Roles admin y fisioterapeuta | Hecho y validado en el servidor. El admin controla la camilla y ve registros. |
| Ver ángulos y altura | Solo estimados en pantalla: no hay sensores, y los actuadores no traen sensor de posición. |
| ESP32 con 5 actuadores (2 cabeza, 2 piernas, altura) | Cabeza (2) funciona con relés. Piernas (2) tiene hardware definido, sin programar. Altura sin definir. |
| Tiempo real con WebSocket | No hay. Se hará cuando el hardware esté estable. La página consulta cada 1 s. |
| Funcionar sin intervención | No todavía: arranque manual y falta paro físico. El servidor ya reabre el USB solo, pero eso falta probarlo en la Raspberry. |

## Flujo actual

```text
Navegador (plantillas/ + publico/css + publico/js)
  GET /api/estado cada 1 s: control, paro, pedidos, ángulos, hardware
  POST /api/...: login, control, mover, detener, paso, paro
      |
servidor.py :8000 (hilos, HTTP/1.0)
  paginas.py: compone el HTML y entrega publico/
  Camilla (memoria + candado): sesiones, titular, paro, ángulos, motor
  vigilar() cada 0.5 s: hombre muerto, ESP32 perdido, titular caído, pedidos vencidos
  basedatos.py -> camilla.db
  hardware.py: Esp32Serial (hilo propio) o Simulador
      | USB serie, 115200
ESP32 con esp32/main.py (MicroPython) -> relés hoy, BTS7960 al final -> actuadores
```

- **Sesión:** un perfil, una sesión. Reiniciar el servidor saca a todos.
- **Control:** un solo titular. Libre: lo toma quien entra. Ocupado: solo lectura y pedido de 30 s. Sin señal 10 s: se libera.
- **Cabeza y altura:** mantener repite `/api/mover` cada 400 ms; soltar envía `/api/detener`.
- **Piernas:** un `/api/paso` por grado (simulado). En modo real está deshabilitada.
- **"Ir a" y "Plano 0°":** bucles en el navegador. En cabeza solo cambian el número; no mueven el actuador.

## Estructura

```text
red/                    instalar_red.sh, encender_red.sh
esp32/main.py           programa del ESP32 (se carga con Thonny como main.py)
compi.txt               código del compañero con BTS7960 (WiFi y PWM). TIENE LA CLAVE DEL WIFI. No se sube.
(encoder/ está en la rama local backup-cambios-esp32: generar_piezas.py, stl/, prueba_encoder.py)
codigoesp32.txt         código original del compañero, solo respaldo. TIENE LA CLAVE DEL WIFI.
web/
  servidor.py, basedatos.py, paginas.py
  hardware.py           Simulador y Esp32Serial
  plantillas/           index.html (esqueleto) y parciales: login, panel/, modales/
  publico/              lo único accesible por HTTP
    css/                tokens, base, botones, secciones, camilla, panel, modales, login, admin
    vendor/             Bootstrap y fuentes
    js/
      main.js, config.js, estado.js, utilidades.js, recepcion.js
      api/              cliente, sondeo, ordenes, admin
      ui/               pintado, dibujo, modales, avisos, formularios, registro
      camilla/          movimiento, mandos, telemetria
      vistas/           acceso, sesion, cesion, pestanas, pacientes, usuarios
```

- Sin compilación: el servidor inserta cada `<!-- incluir: ruta -->` y el navegador carga módulos ES. Los módulos no tienen dependencias circulares.
- `publico/` solo entrega `.css`, `.js` y `.woff2`. `camilla.db` y el código quedan fuera.
- La función de cada archivo está en la sección 10 de `INTEGRACION.md` (falta agregar lo del ESP32).

## Raspberry real

- Usuario `diegocardona`, proyecto en `~/Desktop/Camilla`, rama `esp32-conexion`.
- Python 3.13, pyserial 3.5, permiso `dialout`, `hostapd`, `dnsmasq`, `nft` y `nmcli` instalados. La red Camilla ya está instalada (`/etc/hostapd/camilla.conf`). La lista de "Preparar la Raspberry" salió completa el 09-11.
- El ESP32 aparece como `CP2102` (`10c4:ea60`) en `/dev/ttyUSB0`.
- Se usa con pantalla, teclado y mouse USB, y por SSH desde la laptop.
- **WiFi Meso:** IP `172.17.71.64` por DHCP, puede cambiar. Meso saca a la Raspberry cada 30 s más o menos (`WNM: Disassociation Imminent` en `journalctl`) y por eso se cae el SSH. No es falla de la Raspberry. **El servidor se corre desde una terminal en la pantalla de la Raspberry**, porque si se corta el SSH se apaga. Si hace falta SSH estable, por cable de red.
- El registro del sistema no es persistente: `journalctl -b -1` no muestra el arranque anterior. Reiniciar borra la evidencia, incluido `vcgencmd get_throttled`.
- `Connection closed by ... port 22` suele significar que la Raspberry se está reiniciando.

## ESP32

**Placa:** ESP32 WROOM-32 con CP2102, MicroPython v1.29.0. En la placa hay un `boot.py` sin lógica y nuestro `main.py`. Al abrir el puerto, la placa se reinicia (`rst:0x1`) y en 1 a 2 s imprime `# camilla lista`.

**Módulo de potencia:** se elige con `MODULO` en `esp32/main.py`, y se cambia en Thonny antes de cargar.

- **`"puente"`**, por omisión: BTS7960 (o L298N) para **Piernas** desde el 11-11. Los dos actuadores de Piernas van en paralelo en el mismo BTS7960. Del 09-11 al 11-11 manejó Cabeza en 25 y 26.

  | GPIO | BTS7960 | L298N | Función |
  |---|---|---|---|
  | 26 (`PIN_EXTENDER`) | RPWM | IN1 | Extender |
  | 27 (`PIN_RETRAER`) | LPWM | IN2 | Retraer |
  | `PIN_HABILITAR = None` | R_EN y L_EN a 3.3 V | ENA con jumper | Habilitar. Con un GPIO, se apaga al parar. |

  Cabeza, en el mismo modo, con un L298N y 1 actuador: GPIO 18 (`CABEZA_EXTENDER`) → IN1 y GPIO 19 (`CABEZA_RETRAER`) → IN2, ENA con jumper.

  Usa PWM a 1000 Hz con `VELOCIDAD = 100` %. Las salidas se crean en 0, aunque el PWM de la placa arranque a medias.
- **`"reles"`**: el módulo de 4 relés para **Cabeza**, activo en bajo (`ACTIVO_BAJO = True`), con 26→IN1, 27→IN2, 25→IN3 y 33→IN4. Usa los mismos 26 y 27: no se pueden tener relés y BTS7960 a la vez.

El LED azul (GPIO 2) se enciende mientras hay marcha. Para agregar una sección se edita `SECCIONES`; el servidor la detecta sola, y en la página necesita `continua` y `sinTope` en `config.js`. El modo puente con Cabeza funcionó en la placa real el 09-11. Con Piernas en 26 y 27 se probó el 11-11 en simulación (`probar_puente_piernas.py` y `probar_panel_piernas.py`, sin fallas); falta la placa real.

**Protocolo por USB**, líneas terminadas en `*XX` (XOR en hexadecimal):

```text
Raspberry -> ESP32    M piernas 1 (extender) o M piernas -1 (retraer), repetido cada 200 ms
                      S piernas, X (detener todo), P (sigo aquí)
ESP32 -> Raspberry    E piernas=detenido
```

**Seguridad implementada:**

- Sin `M` durante 500 ms, la sección para sola.
- Pausa de 300 ms antes de volver a arrancar o invertir.
- Watchdog de 2 s, activado con la primera orden válida, para que Thonny pueda entrar antes.
- Sin ESP32: `/api/estado` informa `hardware`, el panel avisa y bloquea, y el servidor no simula.
- Órdenes numeradas (`n`): un `mover` atrasado ya no rearranca el motor.
- **Desde el 09-11** (`99a91cf`): si el ESP32 pasa `SILENCIO_REABRIR` = 3 s sin responder, `hardware.py` cierra y reabre el puerto. Tras abrir espera hasta `ESPERA_ARRANQUE` = 6 s, porque la placa se reinicia. Los avisos son `se perdio la conexion con el ESP32: dejo de responder` y `... no respondio al abrir el puerto (revisa que tenga cargado esp32/main.py)`. Se probó con puerto simulado; en la Raspberry, todavía no.

**Del código del compañero:** se conservó `ParReles`, `poner_rele`, `ACTIVO_BAJO`, la pausa y los pines. Se quitó HTML, WiFi y servidor del puerto 80. Su archivo decía `_init_`; debe ser `__init__`.

## Hardware

**Actuadores** (12 V, con tope interno en los dos extremos, sin sensor de posición):

| Sección | Modelo | Carrera | Velocidad | Corriente |
|---|---|---|---|---|
| Cabeza (2) | ECO-WORTHY 3000N | 150 mm (6") | 5 mm/s | 3 A máxima |
| Piernas (2) | 1500N | 250 mm (10") | 10 mm/s | 4 A |
| Altura | Sin definir | | | |

- **No mezclar modelos en una sección:** uno iría al doble de velocidad y torcería la estructura.
- El tope interno protege el final del actuador, no el de la estructura. Montado, hay que soltar antes de que la camilla llegue a su límite.
- El de Piernas trae un interruptor de polaridad que no se usa.

**Fuente de motores:** 12 V, 40 A, con varios pares de bornes V+ y V−.

**Etapas de potencia:**

1. **Módulo de relés SPDT de 4 canales**, activo en bajo y con `JD-VCC`, solo Cabeza. Era para la presentación, pero ahora se prueba con el puente H. En el firmware necesita `MODULO = "reles"`.
   - Hoy se alimenta por `VIN` del ESP32, y aguantó sin reiniciar la Raspberry.
   - NO a +V con fusible, NC a −V, y cada actuador entre los COM de su par. El −V **no** se une con el GND del ESP32.
   - Fusible: uno de **7.5 A retardado** en el +V de los 4 NO, o los dos de 5 A del plano de relés.
   - TVS **SMBJ24CA**, uno por actuador, entre su cable A y su cable B, cerca del actuador.
2. **Prueba opcional de la app: L298N.** Aguanta unos 2 A por canal, así que no sirve para estos actuadores con carga. Solo con un actuador 3000N, suelto, en un canal:
   - IN1 a GPIO 25, IN2 a GPIO 26, puente de ENA puesto, OUT1 y OUT2 al actuador.
   - 12V a +V con fusible de 3 A. El GND va a −V **y** al GND del ESP32. El 5V queda sin conectar, con el puente del regulador puesto.
   - Usa `MODULO = "puente"`, que ya es el valor por omisión.
   - Revisar que el módulo traiga sus 8 diodos y tocar el disipador durante la prueba.
3. **Definitivo: MD-BTS7960** (43 A, 5.5 a 25 V), **uno por sección**, con los dos actuadores en paralelo: M+ a los cables A y M− a los cables B.
   - Fusible **retardado, uno por módulo, en B+**. Así, si se funde, paran los dos actuadores juntos. **Cabeza 7.5 A y Piernas 10 A**, de vidrio 6 x 30 mm, con portafusible en línea de 15 A o más.
   - Cable de 14 AWG para B+ y B−, y de 16 AWG a los actuadores.
   - Sin TVS al principio: no hay contactos que chispeen y trae diodos internos. Se confirma con la prueba de conteo de errores.
   - Control. Desde el 11-11 Piernas está programada en modo puente con los pines del compañero; Cabeza queda para después, sin programar:

     | Pin del módulo | Piernas (programado) | Cabeza (hoy en L298N) |
     |---|---|---|
     | RPWM (extender) / IN1 | GPIO 26 | GPIO 18 |
     | LPWM (retraer) / IN2 | GPIO 27 | GPIO 19 |
     | R_EN y L_EN / ENA | 3.3 V | jumper puesto |

     El artifact del cableado BTS7960 todavía muestra la propuesta vieja (Cabeza en 25/26/27 y Piernas en 18/19/21). Manda esta tabla.

   - VCC va a 3V3 del ESP32 y GND al GND del ESP32. Si EN va a un GPIO, se pone una resistencia de 10 kΩ de EN a GND, para que el módulo quede apagado mientras arranca el ESP32. R_IS y L_IS quedan sin conectar, porque pueden pasar de 3.3 V.
   - En estas placas el GND de control y el B− suelen estar unidos: comprobarlo con el multímetro.
   - **No conectarlo con `MODULO = "reles"`.**

**Lista de compra:**

- Fusibles 6 x 30 mm retardados: 3 de 7.5 A y 3 de 10 A.
- 2 portafusibles en línea de 6 x 30 mm, de 15 A o más.
- 4 TVS SMBJ24CA, para la presentación con relés. El usuario pensaba comprar 8, pero con el BTS7960 no se necesitan.
- 2 resistencias de 10 kΩ y 2 BTS7960.
- Cable de 14 y 16 AWG.
- Si se usa el L298N: un fusible de 3 A.
- **De la tienda, no sirven:** TVS de 3.3, 5, 9 o 12 V (conducen con 12 V y queman el fusible), el SMBJ170CA y el 1.5KE200CA (no actúan), el SM12C (es para datos), ni un 1N4007 entre los cables del actuador (hace corto al invertir). El P6KE47CA solo sirve como provisional, y el SMF24CA sirve, aunque es más pequeño que el SMBJ24CA.

## Comandos

**La terminal del PC es Git Bash:** las rutas van con `/`. Con `\`, Bash se las come.

```bash
python web/servidor.py                   # con ESP32 por USB
python web/servidor.py --simulador       # sin placa; las 3 secciones simuladas
python web/basedatos.py admin USUARIO    # primer admin, después de crear el perfil
```

Se abre en `http://localhost:8000`. Desde otro equipo se usa `http://IP-DE-LA-RASPBERRY:8000`. Si el ESP32 no se detecta solo: variable `CAMILLA_PUERTO` (por ejemplo `COM5`).

**Subir desde el PC** (nunca `git add .`, por `codigoesp32.txt`):

```bash
git add esp32 web CONTEXTO.md
git commit -m "..."
git push origin esp32-conexion
```

**Bajar en la Raspberry:** `cd ~/Desktop/Camilla && git pull`, con internet. Luego `python3 web/servidor.py` desde la pantalla de la Raspberry.

**Cargar el ESP32 con Thonny**, que también está instalado en la Raspberry:

1. Cerrar el servidor, porque Thonny y el servidor no pueden usar el USB a la vez.
2. Intérprete MicroPython (ESP32) y Stop hasta ver `>>>`.
3. View → Files → `.../esp32/main.py` → clic derecho → **Upload to /**. El 09-11, "Guardar como" pareció funcionar pero no reemplazó el archivo de la placa.
4. Comprobar en la consola de Thonny:

   ```python
   import os; print([(n, "camilla lista" in open(n).read(), "Conectando" in open(n).read()) for n in os.listdir() if n.endswith(".py")])
   ```

   Lo correcto es `[('boot.py', False, False), ('main.py', True, False)]`.
5. Presionar EN: debe salir `# camilla lista`. Si sale `Conectando a ...`, sigue el programa del compañero.

**Encender con la red Camilla:** `cd red && ./encender_red.sh`. ENTER apaga. Los mensajes del servidor quedan en `journalctl -t python3 -f`. No lanzarla por SSH sobre WiFi: toma el WiFi, corta el SSH y, al morir la sesión, se apaga sola. Para hacerlo, usar cable, la pantalla de la Raspberry o `tmux`. Mientras la laptop esté en la red Camilla, no tiene internet.

**Diagnóstico en la Raspberry:**

```bash
uptime -s; vcgencmd get_throttled; ls -l /dev/serial/by-id/     # reinicio, voltaje bajo (0x0 = bien), ESP32 visto
journalctl -k --no-pager --since "2 min ago" | grep -cE "urb stopped|USB disconnect"   # errores USB tras una prueba
journalctl --since "15 min ago" --no-pager | grep -E "Disassociation Imminent|CTRL-EVENT-DISCONNECTED"   # cortes de Meso
sudo fuser -v /dev/ttyUSB0      # quién tiene el puerto
```

El 09-11 quedaron corriendo dos registros en segundo plano: `~/monitor_kernel.txt` y `~/monitor_voltaje.txt`, este con una muestra cada 0.5 s. Para detenerlos:

```bash
pkill -f "vcgencmd get_throttled"
pkill -f "journalctl -kf"
```

## Preparar la Raspberry

Hecho el 09-11 y todo salió bien. Para repetirlo en otra Raspberry, con internet y desde la carpeta del proyecto:

```bash
git fetch origin && git checkout esp32-conexion && git pull

python3 --version                                       # 3.8 o mayor
ls web/hardware.py esp32/main.py                        # deben existir
python3 -c "import serial; print(serial.__version__)"   # si falla: sudo apt install -y python3-serial
id -nG | grep -w dialout                                # si no sale: sudo usermod -aG dialout $USER && sudo reboot
command -v hostapd dnsmasq nft nmcli                    # si falta: sudo apt install -y hostapd dnsmasq-base nftables network-manager
sudo test -e /etc/hostapd/camilla.conf && echo Lista    # si no: cd red && sudo ./instalar_red.sh
ls -l /dev/serial/by-id/                                # con el ESP32 conectado: línea con CP2102 o CH340
```

Si `/dev/ttyUSB0` aparece y desaparece: `sudo apt remove -y brltty`. Los cambios no se copian desde Windows: los `.sh` quedarían con CRLF.

## Problemas encontrados

**Seguridad (comprobados y sin resolver)**

1. Un doble toque en Paro lo libera: el botón alterna sin confirmar.
2. El paro se libera sin sesión, y `POST /api/paro {}` también lo apaga.
3. El paro vive en memoria: reiniciar el servidor lo borra.
4. El hombre muerto del servidor para entre 1.0 y 1.5 s. El ESP32 para en 0.5 s si deja de recibir.

Falta un paro físico que corte la energía de los motores sin depender de ninguna placa. Sin eso no se debe probar con personas. Los actuadores traen tope interno, pero si la estructura llega antes a su límite, el actuador empuja contra ella: hay que soltar el botón.

**Hardware y conexión (09-11)**

- **Ruido en el USB con motores:** con solo los relés hubo 0 errores en 1 minuto; con actuadores, 5, aun con los cables separados. A las 14:48 también se cayó el teclado USB, sin que nadie lo tocara. El kernel registró `cp210x ttyUSB0: usb_serial_generic_read_bulk_callback - urb stopped: -32`, y después de eso Linux deja de leer el puerto hasta reabrirlo. `99a91cf` hace que se recupere, pero no quita el ruido: cada corte detiene el movimiento unos segundos. Causa probable: chispas en los contactos de los relés. Medidas: TVS, separar cables, aislar el módulo con `JD-VCC` y 5 V aparte, ferrita en el USB, y con el BTS7960 se espera menos ruido.
- **Thonny a veces no logra detener nuestro programa:** muestra "Device is busy". La explicación probable es el watchdog. Si la placa ya recibió órdenes, el watchdog está activo: al interrumpir, el programa reinicia la placa a propósito, y en la consola el watchdog la reiniciaría a los 2 s.
  - El 09-11 en la tarde funcionó así: con el servidor apagado, presionar EN para un arranque limpio sin órdenes, y luego Stop.
  - Si aun así falla: usar `mpremote`, o agregar al firmware unos segundos al arrancar en los que se pueda interrumpir.
- **El primer corte de SSH (12:53) no tiene explicación:** no hubo reinicio, voltaje bajo ni eventos de WiFi registrados. Los dos "reinicios" posteriores los hizo el usuario a mano.
- La Raspberry nunca marcó voltaje bajo con el ESP32 y el módulo de relés alimentados por su USB.

**Bloquean lo que falta del hardware**

- Sin sensores, los ángulos de cabeza son estimados: "Ir a" y "Plano 0°" no mueven nada, y los textos de ±1° ya no aplican.
- La estimación de Cabeza llega a 70° en 4.9 s, pero el 3000N tarda unos 30 s en recorrer sus 150 mm. Hay que calibrarla cuando esté montado.
- Al agregar la altura en el firmware, hay que ponerle `sinTope` en `publico/js/config.js`, como a Cabeza y Piernas (ya tiene `continua`). Piernas lo tiene desde el 11-11. Su estimación llega a 45° en unos 3 s, pero el actuador de 1500N tarda unos 25 s en recorrer sus 250 mm: hay que calibrarla al montarlo.
- `Camilla.motor` admite un motor: basta mientras se mueva una sección a la vez.
- Con 2 actuadores por sección y sin sensores pueden desincronizarse un poco. Se corrige solo al llegar a un extremo, por el tope interno.

**Menores**

- Registro de perfiles abierto: con la clave del WiFi se puede mover la camilla. Cerrarlo antes del uso real.
- HTTP sin cifrar, con datos de salud.
- Sin límite de intentos por IP.
- Rechaza `José`, `Peña`, `Ana Lopez` y contraseñas con símbolos.
- La Pi no tiene reloj propio ni NTP en la red Camilla: las fechas pueden salir mal.
- Sin migraciones: una columna nueva no llega a una base ya creada.
- Cargar la página hace 49 peticiones (antes 16). Por túnel de VS Code se quedaba en blanco por pérdida de conexión; se decidió no optimizarlo. En la Pi no se ha medido.

**Conservar:** entrega de archivos limitada a `publico/`, SQL parametrizado, roles validados en el servidor y la máquina de estados del control.

## Decisiones

**Tomadas**

- El admin controla la camilla y ve registros.
- El servidor lo levanta el usuario, desde la pantalla de la Raspberry.
- USB entre Raspberry y ESP32, con `pyserial`. WebSocket va después.
- La red final es local, sin internet.
- `codigoesp32.txt` no se agrega a `.gitignore`; solo sirve de referencia. No se sube.
- Cabeza usa los 2 actuadores 3000N y Piernas los 2 de 1500N.
- Los relés son solo para la presentación. El definitivo es un BTS7960 por sección, con los actuadores en paralelo y un fusible retardado por módulo.
- El servidor reabre el puerto si el ESP32 se queda mudo (`99a91cf`).
- **11-11:** Piernas mide su ángulo con un encoder óptico absoluto en código Gray, hecho por el usuario. El rango de Piernas pasa a ser **0° a 90°**. `CONFIG` y `LIMITES` siguen en 0–45 hasta integrarlo.

**Dejadas para después por el usuario**

- Sensores, "Ir a" y grados reales.
- Finales de carrera propios y tiempo máximo de marcha.
- Arreglo del paro.
- Actualizar `GUIA.md` e `INTEGRACION.md`.
- Cabeza con su propio BTS7960: después de Piernas.

**Pendientes**

1. "Registro": ¿solo cuentas y pacientes, o también historial de uso?
2. Perfiles: ¿registro abierto o los crea el admin?
3. ¿Se deja la sección 11 de `INTEGRACION.md` si el documento se va a evaluar?
4. ¿Cuándo se hace el arranque automático?
5. ¿Qué actuador y qué módulo llevará la altura?
6. ¿Se usará el L298N para probar la app antes del viernes?

## Propuestas (sin aprobar, nada implementado)

**Arreglo del paro:** el botón rojo solo activa; liberar va aparte, con confirmación y sesión; `POST /api/paro` sin `activo` booleano responde 400; se guarda en SQLite.

**Arranque automático:** servicios systemd para red y página, `wlan0` fijo, watchdog de la Pi, microSD protegida, reloj DS3231, dos administradores y una hoja junto a la camilla para reiniciar. Hoy `encender_red.sh` es manual y espera ENTER.

**WebSocket:** `aiohttp` en el mismo puerto (`apt install python3-aiohttp`). Pasa de hilos a asyncio. En la página cambian `api/sondeo.js` y `api/ordenes.js`. Mantener `POST /api/paro` como segunda vía.

**Hardware final, además del BTS7960:** paro de hongo con contactor que corte la fuente de motores. Pines ocupados o reservados (11-11): Piernas 26 y 27; Cabeza 18 y 19; encoder 32, 23 y 34. Para la altura, otro BTS7960 en pines que no choquen con esos (por ejemplo, 25 y 33). Dejar 35, 36 y 39 para sensores; del 34 al 39 son solo de entrada. Evitar 0, 2, 5, 12 y 15, que son pines de arranque. Más adelante, R_IS y L_IS podrían detectar un atasco, con divisor a 3.3 V.

### Encoder de piernas (diseñado el 11-11, sin probar con piezas reales)

Guía visual paso a paso: https://claude.ai/artifact/MAu8PJ5JfVQvSUGJZH4XQU (materiales, impresión, cableado, montaje, Thonny y medidas para la camilla). Fuente local de la guía y de sus imágenes: carpeta temporal de la sesión, no está en el repo.

- **Código:** 6 bits en código Gray, 2° por código. El código k cubre [−19 + 2k, −17 + 2k): 0° es el código 9 y 90° el 54. Cubre de −19° a 109°, con un error máximo de 1°. El código 0 no se fabrica: se lee igual que si no hubiera sector y significa "fuera de rango".
- **Pistas:** el bit 0 va afuera, a 65 mm del eje, y cada bit siguiente 5 mm más adentro, hasta el bit 5 a 40 mm. Las ventanas miden 4 mm de ancho, con 1 mm de material entre pistas. Hay un canal de referencia a 77 mm, fuera del sector, que siempre ve luz. El sector mide 71.5 mm de radio y 3 mm de espesor.
- **Óptica:** 7 LED IR de 3 mm (940 nm) arriba y 7 fototransistores abajo, cada uno detrás de una ranura de 1 × 3 mm. Con luz, el canal lee 0; tapado, lee 1.
- **Electrónica:**
  - LED con 150 Ω a 3.3 V.
  - Fototransistores con 10 kΩ a 3.3 V; se cambian por 22k o 47k si con luz no bajan de 0.8 V.
  - Un 74HC165:
    - A..F = bits 0..5 y G = referencia.
    - H fijo a 3.3 V, y SER y CLK INH a GND.
    - SH/LD al GPIO 32, CLK al GPIO 23 y QH al GPIO 34, con 100 kΩ a GND.
  - Se leen 9 bits: H, G, F..A, SER.
  - Si H no lee 1 o SER no lee 0, es falla de cable o del chip. Si G no lee 0, los LED están apagados.
- **Banco:**
  - Base de 178 × 148 mm, que entra en una cama de 180.
  - Tornillo M8 × 40 con la cabeza trabada abajo, rodamiento 608 en el buje del sector, separador, arandela y tuerca.
  - Horquilla de 2 brazos de 8 mm, con 2 mm de aire a cada lado del sector, atornillada con 2 M3 al soporte de la base.
  - Topes a −15° y 105°.
  - Escala de 2 en 2 grados, con números cada 10.
  - Todo sin soportes. Sector y horquilla en **PLA negro**.
- **Comprobado en el PC** (scripts `verificar.py` y `render.py` en la carpeta temporal, no en el repo):
  - La geometría real del sector, leída cada 0.05° entre −15° y 105° a través de un 74HC165 simulado con `prueba_encoder.py`, da el código correcto, con un error máximo de 1°.
  - La referencia nunca queda tapada.
  - Se detectan los fallos de cable y de LED.
  - Nada choca entre los topes.
  - **Falta todo con piezas reales.**
- **Pendiente:**
  - Medidas de la bisagra para los soportes de la camilla: eje, espacio libre de unos 75 mm de radio, tubos, juego lateral, ángulos reales y fotos.
  - Calibrar `CERO` y `SENTIDO`.
  - Integrarlo a `esp32/main.py`, al protocolo (enviar el ángulo), al servidor y a la página.
  - Pasar `CONFIG`/`LIMITES` de Piernas a 0–90.
- **Si se cambian `BITS`, `GRADOS_POR_CODIGO` o `ANGULO_INICIO`**, hay que cambiarlos igual en `generar_piezas.py` y en `prueba_encoder.py`, y regenerar los STL.

### Sensores de ángulo (conversación del 10-11)

Es para mostrar grados reales, para que "Ir a" y "Plano 0°" muevan de verdad, y para límites por software que protejan la estructura. Hoy el tope interno solo protege al actuador. Cambiaría el firmware (leer y enviar el ángulo), el servidor y la página. Está en lo que el usuario dejó para después: **no se ha tocado código**.

**Qué se necesita medir**

- Cabeza va de −30° a 70° (100° en total) y Piernas de 0° a 45° (`web/publico/js/config.js`).
- Ninguna da una vuelta completa, así que basta un sensor de menos de una vuelta, montado en la bisagra de cada sección. Va uno por sección, no por actuador, así que no detecta si los dos actuadores se desincronizan.
- **Precisión:** para un fisioterapeuta alcanzan unos ±2–3°. Pesa más que la misma posición se repita en cada sesión que el número exacto.
  - Posiciones habituales de Cabeza: semi-Fowler 30–45°, Fowler 45–60°, Fowler alta 60° o más, y Trendelenburg de −10° a −30°.
  - Piernas se elevan entre 15° y 45°.
  - La medición con goniómetro ya tiene unos ±5° de error.
  - Hay que confirmarlo con un fisio del centro: qué ángulos usa, si importa el número exacto o repetir la posición, y si quiere posiciones guardadas.
  - La página muestra pasos de 1° y el objetivo original decía ±1°. Si ±2° basta, conviene cambiar ese texto.
- **Lo que decide el sensor no es la precisión.** Decide que sepa la posición al arrancar (el ESP32 se reinicia al abrir el puerto, por el watchdog o si se va la luz), que detecte un cable cortado y que dure.

**Opciones vistas**

1. **Potenciómetro de 360° sin tope, de plástico conductivo (WDD35D4, 5k o 10k): recomendado para el final.**
   - Sabe la posición siempre y dura millones de ciclos.
   - No tiene tope, así que no se rompe si la bisagra se pasa.
   - Usa 3 cables.
2. **Potenciómetro B10K (el usuario tiene): sirve para probar.** Se conecta igual que el WDD35D4, así que el código servirá para los dos.
   - Ventajas:
     - Sabe la posición siempre.
     - Es simple.
     - Da ±1° fácil: unos 13–15 pasos del ADC por grado.
   - Desventajas:
     - Pista de carbón de unos 10 000 ciclos, así que dura meses.
     - Tiene tope mecánico, por lo que hay que montarlo centrado.
     - Con el desgaste "rasca" y hay que filtrar la lectura.
     - Su eje no aguanta esfuerzo de lado y necesita acople.
     - No es sellado.
   - **Conexión:**
     - Un extremo a **3.3 V, nunca 5 V**, y el otro extremo a GND.
     - El centro al GPIO 34 para Cabeza o al GPIO 35 para Piernas.
     - Un capacitor de 100 nF y una resistencia de 1 MΩ, los dos del centro a GND, cerca del ESP32.
     - Cable trenzado o apantallado, con la malla a GND solo del lado del ESP32.
   - **Montaje:** la sección a mitad de rango (Cabeza a unos 20°) con el potenciómetro a mitad de giro (unos 1.65 V), y el eje alineado con la bisagra mediante un acople.
   - **Calibración:** 2 o 3 puntos medidos con el inclinómetro del celular.
   - **Seguridad:** el rango normal nunca llega a 0 V ni a 3.3 V. Si la lectura llega ahí, es un cable cortado o un corto, y el motor debe parar.
3. **AS5600 magnético:**
   - Ventaja: no tiene contacto, así que no se gasta.
   - Exige que el imán quede centrado a 0.5–3 mm del sensor.
   - Usar la salida analógica OUT: por I2C los dos sensores tienen la misma dirección (0x36).
   - El pin DIR va a GND.
4. **MPU6050 (acelerómetro):**
   - Ventaja: mide la inclinación respecto a la gravedad y no necesita eje.
   - Desventaja: usa I2C con un cable largo junto a los motores, y ya hubo ruido en el USB. Es arriesgado.
5. **HW-040 (encoder mecánico tipo KY-040; el usuario tiene): solo para practicar.**
   - Ventajas:
     - Gira sin tope.
     - Es digital, sin el ADC.
   - Desventajas:
     - Es incremental, así que pierde la posición en cada reinicio y hay que llevar la sección al tope (unos 30 s en Cabeza).
     - Da 18° por paso, o unos 4.5° contando todos los flancos.
     - Rebota y pierde pasos con ruido.
     - No detecta un cable cortado.
     - Se gasta (15 000–30 000 giros).
     - Su código es más complejo.
   - Si se usa: + a 3.3 V, CLK al GPIO 34 y DT al GPIO 35 (el módulo trae pull-ups). Para Piernas, GPIO 36 y 39.
   - **Guardar la posición por código:**
     - Se guardaría en la Raspberry, que no se reinicia con el ESP32, y solo con el motor quieto.
     - Los actuadores no se mueven a mano, por el engranaje sin fin.
     - Resuelve el reinicio al abrir el puerto.
     - No resuelve:
       - Los pasos perdidos, porque se guardaría el valor ya equivocado.
       - Un corte en movimiento.
       - Que nadie puede verificar si el número está bien, y eso es riesgo con paciente.
       - La resolución.
     - Parches posibles:
       - Marcar la posición como dudosa si hubo un reinicio en marcha.
       - Recalibrar en el tope cuando el motor anda y el encoder no cuenta.
       - Usar engranajes.
6. **Encoder óptico diseñado por el usuario (pregunta abierta):**
   - **Incremental** (disco con ranuras y 2 sensores en cuadratura):
     - Ventajas sobre el HW-040: no rebota ni se gasta, y la resolución es libre.
     - Pero pierde la posición igual y no detecta fallas.
     - Se puede agregar una ranura de referencia a mitad del recorrido, para ubicarse con un movimiento corto.
     - No vale la pena.
   - **Absoluto en código Gray: buena opción si el proyecto valora el diseño propio.**
     - Sabe la posición siempre.
     - En código Gray cambia un solo bit por paso.
     - Detecta fallas por saltos imposibles.
     - Necesita 6 pistas y 6 sensores para ±2° (100° / 2° son 50 posiciones), o 7 para 1°.
   - **Diseño:**
     - Un sector de radio grande en vez de un disco completo. Con 100 mm de radio, 1° equivale a 1.75 mm de arco.
     - Sensores de horquilla (H21A1 o módulos LM393), no reflectivos TCRT5000, que fallan con luz ambiente y suciedad.
     - Caja cerrada contra polvo, luz y alcohol.
     - Alimentación a 3.3 V, o un divisor en las salidas si van a 5 V.
     - Un **74HC165** para leer los 6 bits con 3 pines, encadenable entre las dos secciones. Mejor que un expansor I2C.
   - Desventajas frente al WDD35D4: tiempo de diseño, precisión mecánica, y más cables y piezas.

**Recomendación dada:**
- Para probar ya, el B10K.
- Para el final, el WDD35D4, o el óptico absoluto en código Gray si se quiere diseño propio.
- No usar algo incremental (HW-040 u óptico incremental) con pacientes.

## Documentación pendiente

`GUIA.md` e `INTEGRACION.md` no incluyen `esp32/`, `web/hardware.py`, `--simulador`, `n`, `hardware` en `/api/estado`, `python3-serial`, la reapertura del puerto, ni que `SIMULACION` ya no existe. El usuario pidió dejarlo para después.

## Guías publicadas

- Puesta en marcha (pasos, Raspberry, conexiones): https://claude.ai/artifact/HghKdvTRKGM1bepkxkPx92
- Plan general de integración: https://claude.ai/artifact/6Yo3eoRURGcjXuc5KChWrS
- Cableado con relés, fusibles y TVS (presentación): https://claude.ai/artifact/1Gk6CeN5LLnTMpQpNV2bqg
- Cableado final con BTS7960: https://claude.ai/artifact/BPPDzhjXEg8qiHQrK63hmF
- Encoder de piernas (banco de prueba, paso a paso): https://claude.ai/artifact/MAu8PJ5JfVQvSUGJZH4XQU

Son privadas de la cuenta del usuario.

## Para la próxima Claude

- Responder en español. Lo que escribe el usuario manda sobre las guías.
- Decir si algo se puede y cómo antes de modificar, salvo que lo pida directo.
- No crear ni editar `CLAUDE.md`: el usuario prefirió este archivo.
- `GUIA.md` e `INTEGRACION.md` describen solo lo que existe, sin hipótesis ni planes.
- Desde el PC, nada de red o hardware se da por probado.
- Python 3.8+ y solo biblioteca estándar, salvo `pyserial`. El firmware es MicroPython: sin f-strings ni funciones que no existan allí.
- No hacer commit ni push sin que lo pidan.
- **Al guiar en el hardware:** el usuario prefiere pasos numerados que digan dónde se hace cada uno: terminal SSH, pantalla de la Raspberry, Thonny, la mesa o el chat. Hay que pedirle la salida en cada punto de control.
- **Antes de concluir que la Raspberry se reinició sola, preguntar si la reinició el usuario.** El 09-11 eso llevó a dos conclusiones equivocadas.
- Ante algo raro, pedir que no reinicie ni desconecte hasta capturar `uptime -s`, `get_throttled` y `journalctl`.
- Para probar sin tocar el repo: copiar `web/` y `esp32/` a una carpeta temporal, sin `camilla.db`. El firmware corre en CPython con módulos falsos `machine` y `time`; `hardware.serial` se reemplaza por un puerto falso conectado a él. Los scripts (`falsos.py` con `PWM` falso, `probar_esp32.py`, `probar_panel.py`, `probar_reabrir.py` y `probar_puente.py`) estaban en una carpeta temporal y no están en el repo. `probar_esp32.py` y `probar_reabrir.py` esperan `MODULO = "reles"`.
- **Piernas (11-11):** `probar_puente_piernas.py`, `probar_panel_piernas.py` (Chrome real; guion `e3.js`; con `PYTHONIOENCODING=utf-8` en Windows) y la copia `copia_piernas/` están en la carpeta temporal.
- **Encoder:** está en la rama `backup-cambios-esp32`. `encoder/generar_piezas.py` usa `manifold3d` (instalado en un venv de la carpeta temporal). El 11-11 no se pudo ejecutar OpenSCAD descargado: el clasificador lo bloqueó. Las imágenes de la guía salen de un renderizador propio en numpy (`render.py`, en la carpeta temporal).

**Trampas del código**

- `git add .` subiría la clave del WiFi; el repositorio es público.
- `encender_red.sh` filtra el texto de `anotar()` y la línea `"GET / `: cambiar esas frases rompe su monitor.
- `CONFIG.altura.numerica = true` rompe la página con un `TypeError`.
- `LIMITES` y `CONFIG` (`publico/js/config.js`) se cambian juntos, igual que la validación de `basedatos.py`, `ui/formularios.js` y `vistas/acceso.js`.
- `continua` hace que una sección use `mover`, y la telemetría ya no la toca. `sinTope` evita que la página corte el movimiento por su estimación y que deshabilite el botón pulsado.
- Si se deshabilita un botón mientras se mantiene pulsado, puede no llegar el `pointerup`.
- `esp32/main.py` manda en qué secciones existen: las informa en cada línea `E`.
- Una orden `detener` nunca se descarta, aunque su número sea viejo.
- Al abrir el puerto, el ESP32 se reinicia. Por eso `ESPERA_ARRANQUE` (6 s) es mayor que `SILENCIO_REABRIR` (3 s): con menos, se quedaría reabriendo en bucle.
- `avisar()` no repite el mismo mensaje seguido: un fallo que se repite sale una sola vez en la terminal.
- El USB-C de la Pi 4 es solo de alimentación.
- `ESPERA_SOLICITUD` es 35 s en el servidor y 30 s en la página, a propósito.
- `solicitud.usuario` y `respuesta.usuario` traen el nombre para mostrar, no el usuario.
- Los métodos de `Camilla` asumen `candado` tomado; SQLite, PBKDF2 y el puerto serie van fuera.
- Los módulos de `publico/js` leen el DOM al cargarse: un `id` que se quite del HTML rompe el módulo que lo usa.
