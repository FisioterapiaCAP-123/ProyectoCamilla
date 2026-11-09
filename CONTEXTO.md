# Contexto del proyecto

**Fecha:** 08-11-2026. Resumen para retomar el trabajo desde cero: qué se busca, cómo está todo y qué sigue. El detalle del sistema está en `GUIA.md` e `INTEGRACION.md`, pero esas dos **todavía no incluyen la integración del ESP32** (ver "Documentación pendiente").

## Dónde quedamos

- La página ya está separada en plantillas, CSS y módulos JS (con commit).
- El ESP32 quedó integrado por USB para mover los **2 actuadores de cabeza**. Se probó con pines y puerto simulados y en Chrome; **falta probarlo en la placa real**.
- Rama de trabajo: `esp32-conexion`, creada desde `optimizaciones-esp32`. Al escribir esto, esa integración y este archivo estaban sin commit (confirmar con `git status`).

**Siguiente, en orden:**

1. Subir el código desde el PC (ver "Comandos").
2. Bajarlo en la Raspberry y prepararla (ver "Preparar la Raspberry").
3. Cargar `esp32/main.py` a la placa con Thonny.
4. Armar el control sin motores y probar que los relés se apaguen al soltar y al desconectar el USB.
5. Conectar los actuadores uno a la vez, sueltos, y confirmar que los dos van en la misma dirección.
6. Probar juntos, sin nadie sobre la camilla.

## Qué se busca y cómo está

Control remoto web en una Raspberry Pi 4 para la altura, la cabeza y las piernas de una camilla, para uso en un centro de salud. Debe funcionar sin intervención del desarrollador. El PC Windows es solo para desarrollar, porque la Pi es lenta. La red es local, de la propia Raspberry, sin internet.

| Objetivo | Estado |
|---|---|
| Control remoto web | Hecho. Cabeza con motores reales (sin probar en placa); piernas y altura sin actuador. |
| Registro en SQLite | Hay `usuarios` y `pacientes`. No hay bitácora de uso. |
| Roles admin y fisioterapeuta | Hecho y validado en el servidor. El admin controla la camilla y ve registros. |
| Ver ángulos y altura | Solo estimados en pantalla: no hay sensores. |
| ESP32 con 5 actuadores (2 piernas, 2 cabeza, altura) | Hechos los 2 de cabeza. Faltan 3. |
| Tiempo real con WebSocket | No hay; se hará después de que el ESP32 funcione. La página consulta cada 1 s. |
| Funcionar sin intervención | No todavía: el arranque es manual y falta paro físico. |

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
ESP32 con esp32/main.py (MicroPython) -> relés -> actuadores
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

## ESP32

**Hardware conocido:** ESP32 WROOM-32, módulo de relés SPDT de 4 canales (activo en bajo). Está desarmado; el viernes 06-11 movía 2 actuadores con el código del compañero. No se conocen: modelo y voltaje de los actuadores, fuente, finales de carrera, sensores ni si el módulo trae jumper `JD-VCC`.

**Pines:** actuador 1 = GPIO 26 (extender, IN1) y 27 (retraer, IN2). Actuador 2 = GPIO 25 (extender, IN3) y 33 (retraer, IN4). Para agregar actuadores se edita `SECCIONES` en `esp32/main.py`; el servidor y la página detectan las secciones solos.

**Conexiones propuestas**, a confirmar con el compañero:

- USB-A de la Raspberry → USB del ESP32. Datos y energía. No alimentar también por `VIN`.
- `VIN` → `VCC` del módulo, `GND` → `GND`. Si `JD-VCC` trae jumper, se deja.
- Cada cable del actuador a un `COM` distinto de su par. Los dos `NO` a +V, los dos `NC` a −V, con fusible. Así, dos relés activos a la vez solo frenan.
- El −V de los motores no se une con el `GND` del ESP32.

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

**Del código del compañero:** se conservó `ParReles`, `poner_rele`, `ACTIVO_BAJO`, la pausa y los pines. Se quitó HTML, WiFi y servidor del puerto 80. Su archivo decía `_init_`; debe ser `__init__`.

## Comandos

**La terminal del PC es Git Bash:** las rutas van con `/`. Con `\`, Bash se las come.

```bash
python web/servidor.py                   # con ESP32 por USB
python web/servidor.py --simulador       # sin placa; las 3 secciones simuladas
python web/basedatos.py admin USUARIO    # primer admin, después de crear el perfil
```

Se abre en `http://localhost:8000`. Si el ESP32 no se detecta solo: variable `CAMILLA_PUERTO` (por ejemplo `COM5`).

**Subir desde el PC** (nunca `git add .`, por `codigoesp32.txt`):

```bash
git add esp32 web CONTEXTO.md
git commit -m "Integracion del ESP32 por USB para cabeza"
git push -u origin esp32-conexion
```

**Cargar el ESP32:** en Thonny, intérprete MicroPython (ESP32), Stop, abrir `esp32/main.py`, Archivo → Guardar como → Dispositivo MicroPython → `main.py`. Al presionar EN debe salir `# camilla lista`. Thonny y el servidor no pueden usar el USB a la vez.

**Encender con la red Camilla:** `cd red && ./encender_red.sh`. ENTER apaga. Los mensajes del servidor quedan en `journalctl -t python3 -f`.

## Preparar la Raspberry

Con internet: al encender la red Camilla se queda sin él. Desde la carpeta del proyecto:

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

Falta un paro físico que corte la energía de los motores sin depender de ninguna placa. Sin eso no se debe probar con personas. Tampoco hay detección de final de recorrido: hay que soltar el botón.

**Bloquean lo que falta del hardware**

- Sin sensores, los ángulos de cabeza son estimados: "Ir a" y "Plano 0°" no mueven nada, y los textos de ±1° ya no aplican.
- La altura se detiene en la página por estimación a los 1.75 s. Al darle actuador hay que ponerle `continua` y `sinTope`, como a cabeza.
- `Camilla.motor` admite un motor: basta mientras se mueva una sección a la vez.
- Con 2 actuadores por sección sin sensores pueden desincronizarse.

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
- El servidor lo levanta el usuario.
- Los 2 actuadores actuales son de cabeza.
- USB entre Raspberry y ESP32, con `pyserial`. WebSocket va después.
- La red final es local, sin internet.
- `codigoesp32.txt` no se agrega a `.gitignore`; solo sirve de referencia. No se sube.

**Dejadas para después por el usuario**

- Sensores, "Ir a" y grados reales.
- Finales de carrera y tiempo máximo de marcha.
- Arreglo del paro.
- Actualizar `GUIA.md` e `INTEGRACION.md`.

**Pendientes**

1. "Registro": ¿solo cuentas y pacientes, o también historial de uso?
2. ¿Los actuadores traen sensor? Define si habrá números reales.
3. Perfiles: ¿registro abierto o los crea el admin?
4. ¿Se deja la sección 11 de `INTEGRACION.md` si el documento se va a evaluar?
5. ¿Cuándo se hace el arranque automático?

## Propuestas (sin aprobar, nada implementado)

**Arreglo del paro:** el botón rojo solo activa; liberar va aparte, con confirmación y sesión; `POST /api/paro` sin `activo` booleano responde 400; se guarda en SQLite.

**Arranque automático:** servicios systemd para red y página, `wlan0` fijo, watchdog de la Pi, microSD protegida, reloj DS3231, dos administradores y una hoja junto a la camilla para reiniciar. Hoy `encender_red.sh` es manual y espera ENTER.

**WebSocket:** `aiohttp` en el mismo puerto (`apt install python3-aiohttp`). Pasa de hilos a asyncio. En la página cambian `api/sondeo.js` y `api/ordenes.js`. Mantener `POST /api/paro` como segunda vía.

**Hardware final:** relés con `JD-VCC` y fuente de 5 V aparte (VCC a 3V3), paro de hongo con contactor, fusible por actuador, TVS bidireccional en cada motor. Pines propuestos: piernas 23/22 y 21/19, altura 18/13; reservar 32, 34, 35, 36, 39 para sensores.

## Documentación pendiente

`GUIA.md` e `INTEGRACION.md` no incluyen `esp32/`, `web/hardware.py`, `--simulador`, `n`, `hardware` en `/api/estado`, `python3-serial`, ni que `SIMULACION` ya no existe. El usuario pidió dejarlo para después.

## Guías publicadas

- Puesta en marcha (pasos, Raspberry, conexiones): https://claude.ai/artifact/HghKdvTRKGM1bepkxkPx92
- Plan general de integración: https://claude.ai/artifact/6Yo3eoRURGcjXuc5KChWrS

Son privadas de la cuenta del usuario.

## Para la próxima Claude

- Responder en español. Lo que escribe el usuario manda sobre las guías.
- Decir si algo se puede y cómo antes de modificar, salvo que lo pida directo.
- No crear ni editar `CLAUDE.md`: el usuario prefirió este archivo.
- `GUIA.md` e `INTEGRACION.md` describen solo lo que existe, sin hipótesis ni planes.
- Desde el PC, nada de red o hardware se da por probado.
- Python 3.8+ y solo biblioteca estándar, salvo `pyserial`. El firmware es MicroPython: sin f-strings ni funciones que no existan allí.
- No hacer commit ni push sin que lo pidan.
- Para probar sin tocar el repo: copiar `web/` y `esp32/` a una carpeta temporal. El firmware corre en CPython con módulos falsos `machine` y `time`; `hardware.serial` se reemplaza por un puerto falso conectado a él. Los scripts de la sesión anterior estaban en una carpeta temporal y no están en el repo.

**Trampas del código**

- `git add .` subiría la clave del WiFi; el repositorio es público.
- `encender_red.sh` filtra el texto de `anotar()` y la línea `"GET / `: cambiar esas frases rompe su monitor.
- `CONFIG.altura.numerica = true` rompe la página con un `TypeError`.
- `LIMITES` y `CONFIG` (`publico/js/config.js`) se cambian juntos, igual que la validación de `basedatos.py`, `ui/formularios.js` y `vistas/acceso.js`.
- `continua` hace que una sección use `mover`, y la telemetría ya no la toca. `sinTope` evita que la página corte el movimiento por su estimación y que deshabilite el botón pulsado.
- Si se deshabilita un botón mientras se mantiene pulsado, puede no llegar el `pointerup`.
- `esp32/main.py` manda en qué secciones existen: las informa en cada línea `E`.
- Una orden `detener` nunca se descarta, aunque su número sea viejo.
- Al abrir el puerto, el ESP32 se reinicia.
- El USB-C de la Pi 4 es solo de alimentación.
- `ESPERA_SOLICITUD` es 35 s en el servidor y 30 s en la página, a propósito.
- `solicitud.usuario` y `respuesta.usuario` traen el nombre para mostrar, no el usuario.
- Los métodos de `Camilla` asumen `candado` tomado; SQLite, PBKDF2 y el puerto serie van fuera.
- Los módulos de `publico/js` leen el DOM al cargarse: un `id` que se quite del HTML rompe el módulo que lo usa.
