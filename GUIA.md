# Proyecto Camilla — Guía

## Qué hace

- Una **página web** en la Raspberry con 3 botones. Primero se inicia sesión con un **nombre** y una contraseña (de momento acepta cualquiera) para saber quién tiene el control. De momento los botones **no hacen nada**: al presionarlos muestran un error.
- **Solo un dispositivo controla a la vez.** Los demás ven la página bloqueada hasta que toman el control.
- La Raspberry puede crear su **propia red WiFi "Camilla"**. Al conectarse, el celular abre la página solo (como el WiFi de un hotel).

## Archivos

| Archivo | Para qué |
|---|---|
| `web/servidor.py` | Servidor de la página: control de un solo dispositivo |
| `web/login.html` | Inicio de sesión: pide nombre y contraseña y entra al control |
| `web/index.html` | La página de control (botones, tomar/soltar el control) |
| `web/bootstrap/` | Bootstrap 6.0.0-alpha.1 (estilos del inicio de sesión), guardado en el proyecto para no usar internet |
| `red/instalar_red.sh` | Instala hostapd y crea la configuración de la red. Se corre **una vez** con `sudo` |
| `red/encender_red.sh` | Enciende la red "Camilla", muestra quién se conecta; ENTER la apaga |

## Cómo funciona

### Página y servidor
- `servidor.py` corre siempre como servicio de tu usuario (`camilla-web`) y arranca solo al encender la Raspberry. Puerto **8000**.
- Botones 1, 2 y 3: de momento **no están conectados a nada**. Al presionarlos, la página muestra `Error: el boton N todavia no hace nada` sin llamar al servidor.
- Bootstrap está en `web/bootstrap/` y lo entrega el mismo servidor: el inicio de sesión tiene sus estilos también en la red Camilla, que no tiene internet.

### Inicio de sesión (de momento acepta cualquier contraseña)
- `/` muestra `login.html`: se escribe un nombre (máx. 30 letras) y una contraseña, y **Iniciar control** abre `/control?nombre=...`.
- La contraseña **todavía no se comprueba**: se acepta cualquiera (o ninguna) y no se envía al servidor. Para comprobarla de verdad habrá que hacerlo en `servidor.py`.
- El nombre **solo identifica**, no protege nada. Los demás ven "*Diego* tiene el control" y el servidor anota en el registro quién tomó el control.
- Si se abre `/control` sin nombre, la página regresa al inicio de sesión. **Salir** suelta el control y vuelve al inicio.
- Dos personas con el mismo nombre siguen siendo dispositivos distintos (el control lo decide el identificador de cada página, no el nombre).

### Un solo dispositivo con el control
- Cada página abierta tiene un identificador. El servidor guarda cuál tiene el control.
- **Tomar el control** → confirmación en la página → el otro dispositivo queda bloqueado.
- Solo el dispositivo que tiene el control ve los botones activos.
- La página pregunta el estado cada 1,5 s; por eso el otro celular se bloquea en uno o dos segundos.
- El control se libera con **Soltar el control** o tras **60 s** sin contacto de esa página (la cerró, bloqueó el celular o salió del WiFi).
- Ajuste en `servidor.py`: `TIEMPO_LIBERAR` (60 s).

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

**Encender la red:**
```bash
cd ~/Desktop/"Proyecto Camilla"/red
./encender_red.sh
```
Pide la contraseña de `sudo`, muestra la clave del WiFi. Conecta el celular a **Camilla**: la página se abre sola, o entra a `http://10.42.0.1`. **ENTER** apaga la red y vuelve al WiFi anterior.

**Usar la página sin la red Camilla** (en la Raspberry): `http://localhost:8000`. Dos pestañas sirven para probar el control (cada pestaña cuenta como un dispositivo).

**Comandos útiles:**

| Para | Comando |
|---|---|
| Ver si el servidor corre | `systemctl --user status camilla-web` |
| Aplicar cambios de `servidor.py` | `systemctl --user restart camilla-web` |
| Ver mensajes del servidor en vivo | `journalctl -t python3 -f` |
| Ver la clave del WiFi | `sudo grep wpa_passphrase /etc/hostapd/camilla.conf` |
| Cambiar la clave (mín. 8 caracteres) | `sudo nano /etc/hostapd/camilla.conf` → línea `wpa_passphrase=` |

**Hacer cambios en la página o el servidor:**

| Si cambias... | Qué hacer |
|---|---|
| `login.html` o `index.html` | Guardar y **recargar la página** en el navegador. No hace falta reiniciar. |
| `servidor.py` | Reiniciar el servicio: `systemctl --user restart camilla-web` |

- Los `.html` se leen cada vez que alguien abre la página, así que siempre se ve la versión guardada.
- `servidor.py` solo se lee al arrancar. Al reiniciarlo, quien tenga el control lo pierde (tendrá que volver a tomarlo).
- Si en el celular sigue saliendo la versión vieja después de recargar, es la caché del navegador: cerrar la pestaña y abrirla de nuevo.

## Problemas conocidos

- **Xiaomi/Android se desconecta "por no tener internet":** apagar el cambio automático a datos móviles (Ajustes → Wi-Fi → Asistente de Wi-Fi) y elegir mantener la conexión.
- **iPhone:** al cerrar la ventana de la página, elegir **"Usar sin Internet"**.
- **La página no carga escribiendo la dirección:** escribir `http://` al inicio (sin eso, algunos navegadores intentan `https`).
- **Si se cerró la terminal con la red encendida y no vuelve el internet:**
  ```bash
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
| El servidor automático | `systemctl --user disable --now camilla-web`, `rm ~/.config/systemd/user/camilla-web.service` y `loginctl disable-linger` |
| El reporte de pruebas | `rm ~/reporte_red.txt` |
| El proyecto | Borrar las carpetas `web/` y `red/` y esta guía |

Si quitas hostapd, `encender_red.sh` deja de funcionar. Si quitas el servidor automático, la página se puede seguir abriendo a mano con `python3 web/servidor.py`.

## Cambios en el sistema (fuera de la carpeta del proyecto)

| Fecha | Cambio | Dónde | Estado | Cómo deshacer |
|---|---|---|---|---|
| 21-10-2026 | Servicio que arranca la página al encender | `~/.config/systemd/user/camilla-web.service` | Activo | `systemctl --user disable --now camilla-web` y borrar el archivo |
| 21-10-2026 | "Linger": el servicio arranca sin iniciar sesión | `/var/lib/systemd/linger/diegocardona` | Activo | `loginctl disable-linger` |
| 21-10-2026 | Programa hostapd | Paquete del sistema (`apt`) | Instalado | `sudo apt purge hostapd` |
| 21-10-2026 | Configuración de la red (incluye la clave, solo la lee root) | `/etc/hostapd/camilla.conf` | Activo | `sudo rm -f /etc/hostapd/camilla.conf` |
| 21-10-2026 | Reporte de pruebas de la red | `~/reporte_red.txt` | Crece con cada prueba | `rm ~/reporte_red.txt` |
| 21-10-2026 | Perfil "Camilla" de NetworkManager | `/etc/NetworkManager/system-connections/` | **Ya borrado** (no funcionaba) | — |

**Solo mientras la red está encendida** (el script lo quita al presionar ENTER): `wlan0` fuera de NetworkManager, IP `10.42.0.1`, procesos `hostapd` y `dnsmasq`, tabla `nft` "camilla".

No se instaló nada más ni se cambió la red "Meso".
