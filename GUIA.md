# Proyecto Camilla — Guía

## Qué hace

- Una **página web** en la Raspberry con el panel de la camilla: inicio de sesión con **tu nombre** y la **contraseña del panel** (una sola para todos), dibujo de la camilla, botones de altura, cabeza y piernas, "Plano 0°" y **paro de emergencia**. El diseño y sus reglas vienen de `INTEGRACION.md`.
- De momento **no hay motores**: el panel funciona en **simulación** (el dibujo se mueve, la camilla no).
- **Una sola persona controla la camilla a la vez.** Los demás la ven en solo lectura y pueden **pedir el control**; quien lo tiene decide si lo pasa.
- La Raspberry puede crear su **propia red WiFi "Camilla"**. Al conectarse, el celular abre la página solo (como el WiFi de un hotel).

## Archivos

| Archivo | Para qué |
|---|---|
| `web/servidor.py` | Servidor de la página: sesiones, control, paro y órdenes de movimiento (simuladas) |
| `web/index.html` | El panel completo en una sola página: inicio de sesión, control y avisos |
| `web/clave.py` | Pone o cambia la contraseña del panel |
| `web/clave.json` | La contraseña del panel, cifrada. **No se sube a git** (está en `.gitignore`) |
| `web/vendor/` | Bootstrap 5.3.3 y las fuentes (Barlow Condensed, IBM Plex), guardados en el proyecto para no usar internet |
| `INTEGRACION.md` | Contrato del diseño (reglas del control, mensajes). Aquí esos mensajes van por HTTP, no por WebSocket |
| `red/instalar_red.sh` | Instala hostapd y crea la configuración de la red. Se corre **una vez** con `sudo` |
| `red/encender_red.sh` | Enciende la red "Camilla" y la página, muestra quién se conecta; ENTER apaga las dos |

## Cómo funciona

### Página y servidor
- `servidor.py` **no arranca solo**: lo enciende `encender_red.sh` junto con la red, y ENTER lo apaga. Para probar sin la red se corre a mano (ver **Uso**). Puerto **8000**. Corre con tu usuario, sin `sudo`.
- Todo es HTTP con lo que ya trae Python, sin WebSocket y sin instalar nada:
  - La página pregunta `GET /api/estado` **cada segundo**: quién tiene el control, paro, pedidos de control, posición.
  - Las órdenes van por `POST`: `/api/login`, `/api/logout`, `/api/control/tomar`, `/api/control/solicitar`, `/api/control/cancelar`, `/api/control/responder`, `/api/control/liberar`, `/api/mover`, `/api/detener`, `/api/paso` y `/api/paro`.
  - Por eso los avisos llegan a los otros celulares en uno o dos segundos.
- Si la página no recibe respuesta 3 veces seguidas, muestra **"Sin conexión con la camilla"** y bloquea el movimiento.
- Bootstrap y las fuentes están en `web/vendor/` y los entrega el mismo servidor: el panel se ve igual en la red Camilla, que no tiene internet.
- La página se ve siempre en **modo claro**, aunque el celular esté en modo oscuro (`color-scheme: only light` y `data-bs-theme="light"`).

### Inicio de sesión
- Cada quien escribe **su nombre** (de 1 a 30 letras) y la **contraseña del panel**, que es la misma para todos.
- El nombre solo sirve para ver quién tiene el control. La contraseña evita que entre cualquiera que esté en la red.
- La contraseña se guarda **cifrada** (PBKDF2) en `web/clave.json`, nunca en texto. Se pone o se cambia con `web/clave.py` (ver **Uso**).
- Con la contraseña mala sale "Contraseña incorrecta." y el servidor espera 1 s antes de contestar (frena a quien intente adivinarla).
- **Los nombres no se repiten:** si alguien ya está conectado como "Ana", nadie más puede entrar como "Ana" (tampoco "ana"). Así nadie se queda con el control de otro sin pedirlo. Cuando "Ana" lleva 10 s sin dar señales, el nombre queda libre.
- La sesión es **por pestaña**: recargar la página no la cierra, pero cerrar la pestaña sí. Dos pestañas sirven para probar con dos nombres.
- Si el servidor se reinicia, todas las sesiones se pierden y la página vuelve al inicio de sesión.
- Con una sola contraseña para todos: si alguien deja de tener permiso, hay que cambiarla.

### Quién tiene el control
- El control es de una **persona** (el nombre con que entró), no del celular.
- Al entrar: si nadie lo tiene, te lo quedas. Si otra persona lo tiene, entras en **solo lectura** y la página te ofrece **Solicitar el control**.
- Al pedirlo, a quien lo tiene le sale un aviso con **Permitir / No permitir** y 30 s para decidir. Si no contesta, cuenta como **no**: el control nunca se pasa por silencio.
- Si alguien suelta el control (o sale) mientras otro lo está pidiendo, pasa directo a quien lo pidió.
- Si quien tiene el control **deja de dar señales 10 s** (cerró la página, bloqueó el celular o salió del WiFi), el servidor lo libera.
- Cada vez que el control cambia de persona, el servidor para los motores.
- **Bloquear** (arriba a la derecha) solo bloquea los botones de esa pantalla.

### Paro de emergencia
- Lo puede activar **cualquiera**, tenga el control o no, e incluso sin haber entrado: está el botón rojo del inicio de sesión y la tecla **Esc**.
- El paro es uno solo para todos: llega a todas las pantallas y bloquea el movimiento hasta que alguien lo libera.

### Simulación (mientras no haya motores)
- `SIMULACION = True` en `servidor.py`. Las órdenes se revisan (solo quien tiene el control puede mover y nadie mueve con el paro activo) y se anotan en el registro, pero no mueven nada.
- El servidor guarda los ángulos simulados de cabeza y piernas: todas las pantallas ven la misma posición.
- La altura no tiene sensor: su barra es solo un dibujo, como en el diseño.
- **Hombre muerto:** mientras se mantiene un botón de altura, la página repite la orden; si deja de llegar 1 s, el servidor para el motor solo.
- Cuando haya motores: `SIMULACION = False` y poner las órdenes reales en `parar_motores`, `mover`, `detener` y `paso` de `servidor.py`.
- Ajustes en `servidor.py`: `TIEMPO_LIBERAR` (10 s), `ESPERA_SOLICITUD` (35 s), `HOMBRE_MUERTO` (1 s) y `LIMITES` de los ángulos (deben coincidir con `CONFIG` en `index.html`).

### Red WiFi "Camilla"
- La crea **hostapd**: WPA2, canal 6 (2,4 GHz). Nombre y clave en `/etc/hostapd/camilla.conf`.
- Mientras está encendida:
  - La Raspberry es `10.42.0.1` y **se queda sin internet** (tiene una sola antena WiFi).
  - `dnsmasq` da IPs `10.42.0.10`–`10.42.0.254` y contesta que cualquier sitio de internet está en la Raspberry.
  - Una regla `nft` pasa el puerto 80 al 8000.
  - El servidor redirige las comprobaciones de internet de los celulares a la página → el celular la abre solo.
- **Por qué hostapd y no NetworkManager:** con este chip WiFi (Raspberry Pi 4), NetworkManager agrega a la red opciones (SHA256/WPA3) que el chip no maneja, y los celulares no se conectaban con clave.
- Cada vez que se apaga la red, se agrega un reporte a `~/reporte_red.txt`.

## Uso

**Cambiar la contraseña del panel** (ya hay una puesta; sin ella no entra nadie):
```bash
cd ~/Desktop/"Proyecto Camilla"
python3 web/clave.py
```
Pide la nueva dos veces (mínimo 6 caracteres). No hace falta reiniciar el servidor. Si se olvida, no se puede ver: se pone una nueva con este mismo comando.

**Encender la red:**
```bash
cd ~/Desktop/"Proyecto Camilla"/red
./encender_red.sh
```
Pide la contraseña de `sudo` (no escribas `sudo` antes del script), enciende la red y la página, y muestra la clave del WiFi. Conecta el celular a **Camilla**: la página se abre sola, o entra a `http://10.42.0.1`. En la terminal se ve quién se conecta, quién entra al panel, quién tiene el control y el paro. **ENTER** apaga la red y la página y vuelve al WiFi anterior.

**Usar la página sin la red Camilla** (en la Raspberry):
```bash
cd ~/Desktop/"Proyecto Camilla"
python3 web/servidor.py
```
Abre `http://localhost:8000`. **Ctrl+C** apaga la página. Dos pestañas sirven para probar el control con dos nombres.

**Comandos útiles:**

| Para | Comando |
|---|---|
| Cambiar la contraseña del panel | `python3 web/clave.py` |
| Ver si la página está encendida | `ss -ltn 'sport = :8000'` (si sale `LISTEN`, está encendida) |
| Ver mensajes de la página en vivo (con la red encendida) | `journalctl -t python3 -f` |
| Ver la clave del WiFi | `sudo grep wpa_passphrase /etc/hostapd/camilla.conf` |
| Cambiar la clave (mín. 8 caracteres) | `sudo nano /etc/hostapd/camilla.conf` → línea `wpa_passphrase=` |

**Hacer cambios en la página o el servidor:**

| Si cambias... | Qué hacer |
|---|---|
| `index.html` | Guardar y **recargar la página** en el navegador. No hace falta reiniciar. |
| `servidor.py` | Apagar y volver a encender la página: ENTER y otra vez `./encender_red.sh`, o **Ctrl+C** y otra vez `python3 web/servidor.py` |
| La contraseña del panel | Nada: el servidor lee `clave.json` en cada inicio de sesión. |

- Los archivos de la página se leen cada vez que alguien la abre, así que siempre se ve la versión guardada.
- `servidor.py` solo se lee al arrancar. Al reiniciarlo se pierden las sesiones y el control: todos vuelven al inicio de sesión.
- Si en el celular sigue saliendo la versión vieja después de recargar, es la caché del navegador: cerrar la pestaña y abrirla de nuevo.

## Problemas conocidos

- **Xiaomi/Android se desconecta "por no tener internet":** apagar el cambio automático a datos móviles (Ajustes → Wi-Fi → Asistente de Wi-Fi) y elegir mantener la conexión.
- **iPhone:** al cerrar la ventana de la página, elegir **"Usar sin Internet"**.
- **Android: "Usar esta red como está" cierra la ventana de la página.** Para seguir, usar la página dentro de esa ventana sin tocar el menú, o abrir `http://10.42.0.1` en el navegador con los **datos móviles apagados**.
- **Bloquear el celular de quien tiene el control** lo libera a los 10 s (la página deja de dar señales). Es a propósito: la camilla no puede quedar tomada por una pantalla apagada.
- **La página no carga escribiendo la dirección:** escribir `http://` al inicio (sin eso, algunos navegadores intentan `https`).
- **Si se cerró la terminal con la red encendida y no vuelve el internet:**
  ```bash
  pkill -f web/servidor.py
  sudo pkill -F /run/camilla-hostapd.pid
  sudo pkill -F /run/camilla-dnsmasq.pid
  sudo nft destroy table ip camilla
  sudo ip addr flush dev wlan0
  nmcli device set wlan0 managed yes
  ```

## Cómo quitarlo

Se puede quitar cada parte por separado:

| Quitar | Comandos |
|---|---|
| La red WiFi "Camilla" | `sudo apt purge hostapd` y `sudo rm -f /etc/hostapd/camilla.conf` |
| El reporte de pruebas | `rm ~/reporte_red.txt` |
| El proyecto | Borrar las carpetas `web/` y `red/`, esta guía e `INTEGRACION.md` (la contraseña del panel está dentro de `web/`) |

Si quitas hostapd, `encender_red.sh` deja de funcionar; la página se puede seguir abriendo a mano con `python3 web/servidor.py`.

## Cambios en el sistema (fuera de la carpeta del proyecto)

**Estado actual (29-10-2026):**
- **Instalado:** el paquete `hostapd`, `/etc/hostapd/camilla.conf` y `~/reporte_red.txt`. El servicio propio de `hostapd` que trae Debian está `masked`: nunca arranca solo.
- **Nada arranca solo** al encender la Raspberry. La red y la página se encienden a mano con `encender_red.sh`.
- **No hay** servicios de systemd del proyecto, reglas de `sudo` o polkit, ni tareas programadas (cron).
- El panel nuevo (29-10-2026) no cambió nada del sistema: Bootstrap, fuentes y la contraseña del panel están dentro de la carpeta del proyecto, y el servidor solo usa lo que ya trae Python.
- Para el producto terminado se hará que todo arranque solo. Cuando se haga, se anotará aquí.

| Fecha | Cambio | Dónde | Estado | Cómo deshacer |
|---|---|---|---|---|
| 21-10-2026 | Servicio que arranca la página al encender | `~/.config/systemd/user/camilla-web.service` | **Quitado** el 28-10-2026 | — |
| 21-10-2026 | "Linger": el servicio arranca sin iniciar sesión | `/var/lib/systemd/linger/diegocardona` | **Quitado** el 28-10-2026 | — |
| 21-10-2026 | Programa hostapd | Paquete del sistema (`apt`) | Instalado | `sudo apt purge hostapd` |
| 21-10-2026 | Configuración de la red (incluye la clave, solo la lee root) | `/etc/hostapd/camilla.conf` | Activo | `sudo rm -f /etc/hostapd/camilla.conf` |
| 21-10-2026 | Reporte de pruebas de la red | `~/reporte_red.txt` | Crece con cada prueba | `rm ~/reporte_red.txt` |
| 21-10-2026 | Perfil "Camilla" de NetworkManager | `/etc/NetworkManager/system-connections/` | **Ya borrado** (no funcionaba) | — |

**Solo mientras la red está encendida** (el script lo quita al presionar ENTER): `wlan0` fuera de NetworkManager, IP `10.42.0.1`, procesos `hostapd` y `dnsmasq`, tabla `nft` "camilla" y la página (`servidor.py`).

No se instaló nada más ni se cambió la red "Meso".
