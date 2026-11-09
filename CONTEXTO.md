# Contexto del proyecto

**Fecha:** 09-11-2026. Resumen para retomar el trabajo desde cero: qué se busca, cómo está todo y qué sigue. El detalle del sistema está en `GUIA.md` e `INTEGRACION.md`, pero esas dos **todavía no incluyen la integración del ESP32** (ver "Documentación pendiente").

## Dónde quedamos

- **09-11: primera prueba real completa.** La cadena página → Raspberry → USB → ESP32 → módulo de relés → actuadores funcionó: se movieron. Al desconectar el USB, la página avisa "Sin conexión con los motores" y los relés se apagan. Al reconectarlo, vuelve solo.
- Con los motores en marcha aparecen **errores USB** (`urb stopped: -32`) que dejaban el puerto mudo hasta reiniciar el servidor. `web/hardware.py` ya reabre el puerto solo (commit `99a91cf`, en GitHub). **Falta bajarlo en la Raspberry y probarlo con motores.**
- El módulo de relés es **solo para la presentación del viernes 13-11-2026**. El definitivo es **un BTS7960 por sección** (ver "Hardware").
- **09-11, tarde:** el compañero actualizó su código para manejar un puente H (L298N o BTS7960) en los pines 25 y 26. `esp32/main.py` se adaptó: ahora usa `MODULO = "puente"` por omisión, y los relés quedan como opción. Al escribir esto estaba sin commit (confirmar con `git status`).
- Rama `esp32-conexion`, en GitHub en `99a91cf`. En el PC la rama sigue enlazada a `origin/optimizaciones-esp32`, así que hay que subir con `git push origin esp32-conexion`.

**Siguiente, en orden:**

1. **En la Raspberry:** `git pull` con internet y cargar el nuevo `esp32/main.py` con Thonny, en modo puente. Después, levantar el servidor desde la pantalla de la Raspberry y probar Cabeza con el puente H. Al cortarse debe salir `se perdio la conexion con el ESP32: dejo de responder` y, unos segundos después, `ESP32 conectado`, sin reiniciar nada.
2. **Comprar** lo de la "Lista de compra".
3. **Presentación:** relés con fusible y TVS, solo Cabeza. Opcional: probar la app con un L298N y un solo actuador 3000N sin carga.
4. **Detener los registros** que quedaron corriendo en la Raspberry (ver "Diagnóstico").
5. **Después del viernes:** agregar Piernas en el firmware y en la página, y probar con BTS7960.
6. **Resolver cómo recargar el firmware** cuando Thonny no logra detener el programa (ver "Problemas").

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

- **`"puente"`**, por omisión desde el 09-11: L298N o BTS7960, con los mismos pines del código nuevo del compañero. Los dos actuadores de Cabeza van en paralelo en el mismo canal.

  | GPIO | L298N | BTS7960 | Función |
  |---|---|---|---|
  | 25 (`PIN_EXTENDER`) | IN1 | RPWM | Extender |
  | 26 (`PIN_RETRAER`) | IN2 | LPWM | Retraer |
  | `PIN_HABILITAR = None` | ENA con jumper | R_EN y L_EN a 3.3 V | Habilitar. Con un GPIO, se apaga al parar. |

  Usa PWM a 1000 Hz con `VELOCIDAD = 100` %. Las salidas se crean en 0, aunque el PWM de la placa arranque a medias.
- **`"reles"`**: el módulo de 4 relés, activo en bajo (`ACTIVO_BAJO = True`), con 26→IN1, 27→IN2, 25→IN3 y 33→IN4.

El LED azul (GPIO 2) se enciende mientras hay marcha. Para agregar una sección se edita `SECCIONES`; el servidor y la página la detectan solos. El modo puente se probó el 09-11 con placa y PWM simulados, sin fallas. **Falta probarlo en la placa real.**

**Protocolo por USB**, líneas terminadas en `*XX` (XOR en hexadecimal):

```text
Raspberry -> ESP32    M cabeza 1 (extender) o M cabeza -1 (retraer), repetido cada 200 ms
                      S cabeza, X (detener todo), P (sigo aquí)
ESP32 -> Raspberry    E cabeza=detenido
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
   - Control. Cabeza ya está programada en modo puente; Piernas es una propuesta sin programar:

     | Pin del módulo | Cabeza | Piernas |
     |---|---|---|
     | RPWM (extender) | GPIO 25 | GPIO 18 |
     | LPWM (retraer) | GPIO 26 | GPIO 19 |
     | R_EN y L_EN, unidos | 3.3 V, o GPIO 27 con `PIN_HABILITAR` | GPIO 21 |

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
- **Thonny no logra detener nuestro programa:** muestra "Device is busy" y Stop no entra. Habrá que resolverlo antes de cargar el firmware del BTS7960. Ideas sin probar: presionar EN y enseguida Stop, usar `mpremote`, o agregar al firmware unos segundos al arrancar en los que se pueda interrumpir.
- **El primer corte de SSH (12:53) no tiene explicación:** no hubo reinicio, voltaje bajo ni eventos de WiFi registrados. Los dos "reinicios" posteriores los hizo el usuario a mano.
- La Raspberry nunca marcó voltaje bajo con el ESP32 y el módulo de relés alimentados por su USB.

**Bloquean lo que falta del hardware**

- Sin sensores, los ángulos de cabeza son estimados: "Ir a" y "Plano 0°" no mueven nada, y los textos de ±1° ya no aplican.
- La estimación de Cabeza llega a 70° en 4.9 s, pero el 3000N tarda unos 30 s en recorrer sus 150 mm. Hay que calibrarla cuando esté montado.
- Al agregar Piernas o altura en el firmware, hay que ponerles `continua` y `sinTope` en `publico/js/config.js`, como a cabeza. Piernas hoy usa `paso`.
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

**Dejadas para después por el usuario**

- Sensores, "Ir a" y grados reales.
- Finales de carrera propios y tiempo máximo de marcha.
- Arreglo del paro.
- Actualizar `GUIA.md` e `INTEGRACION.md`.
- Agregar Piernas: después de la presentación, salvo que el usuario diga otra cosa.

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

**Hardware final, además del BTS7960:** paro de hongo con contactor que corte la fuente de motores. Para la altura, otro BTS7960 en pines libres que no choquen con 18, 19, 21, 25, 26 y 27. Reservar 32, 34, 35, 36 y 39 para sensores; del 34 al 39 son solo de entrada. Más adelante, R_IS y L_IS podrían detectar un atasco, con divisor a 3.3 V.

## Documentación pendiente

`GUIA.md` e `INTEGRACION.md` no incluyen `esp32/`, `web/hardware.py`, `--simulador`, `n`, `hardware` en `/api/estado`, `python3-serial`, la reapertura del puerto, ni que `SIMULACION` ya no existe. El usuario pidió dejarlo para después.

## Guías publicadas

- Puesta en marcha (pasos, Raspberry, conexiones): https://claude.ai/artifact/HghKdvTRKGM1bepkxkPx92
- Plan general de integración: https://claude.ai/artifact/6Yo3eoRURGcjXuc5KChWrS
- Cableado con relés, fusibles y TVS (presentación): https://claude.ai/artifact/1Gk6CeN5LLnTMpQpNV2bqg
- Cableado final con BTS7960: https://claude.ai/artifact/BPPDzhjXEg8qiHQrK63hmF

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
