# Proyecto Camilla: guía del sistema

**Proyecto:** camilla automatizada, Universidad Mesoamericana  
**Última actualización:** 08-11-2026  
**Referencia técnica:** [INTEGRACION.md](INTEGRACION.md)

Esta guía explica qué hace el sistema, cómo está construido y cómo se instala, se opera y se desinstala. Las rutas de la API, los formatos de los mensajes, los parámetros y el esquema de la base de datos están en la referencia técnica.

## Contenido

1. [Descripción general](#1-descripción-general)
2. [Arquitectura](#2-arquitectura)
3. [Estructura del repositorio](#3-estructura-del-repositorio)
4. [Requisitos](#4-requisitos)
5. [Instalación en la Raspberry Pi](#5-instalación-en-la-raspberry-pi)
6. [Operación](#6-operación)
7. [Funcionamiento](#7-funcionamiento)
8. [Red WiFi Camilla](#8-red-wifi-camilla)
9. [Datos y seguridad](#9-datos-y-seguridad)
10. [Mantenimiento](#10-mantenimiento)
11. [Solución de problemas](#11-solución-de-problemas)
12. [Desinstalación](#12-desinstalación)
13. [Cambios en el sistema operativo](#13-cambios-en-el-sistema-operativo)
14. [Glosario](#14-glosario)

## 1. Descripción general

El sistema es una aplicación web instalada en una Raspberry Pi 4 que funciona como control remoto de la camilla. Desde el navegador de un celular, una tablet o un computador se ordena subir o bajar la altura, la cabeza y las piernas, y se observa la posición en pantalla.

Funciones disponibles:

- **Panel de control:** dibujo de la camilla, botones de altura, cabeza y piernas, posicionamiento por ángulo ("Ir a"), "Plano 0°" y paro de emergencia.
- **Perfiles:** cada persona entra con su propio usuario y contraseña.
- **Roles:** fisioterapeuta y administrador.
- **Administración:** registros de pacientes y gestión de perfiles, solo para administradores.
- **Control exclusivo:** una sola persona mueve la camilla a la vez. Las demás la ven en solo lectura y pueden pedir el control.
- **Red propia:** la Raspberry puede crear la red WiFi "Camilla". Al conectarse, el celular abre la página automáticamente.

> **Estado actual: simulación.** No hay motores, ESP32, sensores ni finales de carrera conectados. Las órdenes se validan y se registran y el dibujo se mueve, pero la camilla física no. El detalle está en [Simulación](#76-simulación).

## 2. Arquitectura

```text
  Celular, tablet o PC                   Raspberry Pi 4
 +---------------------+          +-------------------------------------------+
 | Navegador           |   HTTP   | web/servidor.py (puerto 8000)             |
 | web/index.html      |<-------->|   Entrega la página y atiende las órdenes |
 +---------------------+   WiFi   |   Reglas del control y estado en memoria  |
                                  |   Vigilancia de seguridad cada 0.5 s      |
                                  |   web/basedatos.py --> web/camilla.db     |
                                  +-------------------------------------------+
                                  | Red: hostapd, dnsmasq, nftables           |
                                  +-------------------------------------------+
```

| Componente | Archivos o programas | Función |
|---|---|---|
| Panel web | `web/index.html`, `web/vendor/` | Interfaz completa en una sola página. Bootstrap 5.3.3 y las fuentes se entregan desde la propia Raspberry, porque la red Camilla no tiene internet. |
| Servidor | `web/servidor.py` | Entrega la página, atiende las órdenes, aplica las reglas del control y guarda el estado compartido. Usa solo la biblioteca estándar de Python. |
| Base de datos | `web/basedatos.py`, `web/camilla.db` | Perfiles y registros de pacientes en SQLite. |
| Red | `red/instalar_red.sh`, `red/encender_red.sh`, `hostapd`, `dnsmasq`, `nftables` | Crea la red WiFi, entrega direcciones IP y dirige a los celulares hacia la página. |

**Comunicación.** Todo va por HTTP; no se usa WebSocket.

- La página consulta `GET /api/estado` cada segundo para saber quién tiene el control, si hay paro, si hay pedidos de control y cuál es la posición. Esta consulta también corre en la pantalla de inicio de sesión.
- Cada orden se envía con una petición `POST`: iniciar sesión, tomar el control, mover, paro.
- Con este esquema, un cambio hecho desde una pantalla llega a las demás en uno o dos segundos.

**Dónde se guarda cada dato.**

| Dato | Ubicación | Duración |
|---|---|---|
| Perfiles y registros de pacientes | `web/camilla.db` | Permanente. Se conserva al reiniciar. |
| Sesiones abiertas | Memoria del servidor | Se pierden al reiniciar el servidor: todos vuelven al inicio de sesión. |
| Titular del control y pedidos pendientes | Memoria del servidor | Se pierden al reiniciar el servidor: el control queda libre. |
| Estado del paro de emergencia | Memoria del servidor | Se pierde al reiniciar el servidor: el paro queda inactivo. |
| Ángulos simulados de cabeza y piernas | Memoria del servidor | Vuelven a 0° al reiniciar el servidor. |
| Altura mostrada | Memoria de cada página | Vuelve a media carrera al recargar la página. |

## 3. Estructura del repositorio

```text
.
├── README.md
├── GUIA.md                     Esta guía
├── INTEGRACION.md              Referencia técnica
├── .gitignore
├── red/
│   ├── instalar_red.sh         Instala hostapd y crea la configuración de la red
│   └── encender_red.sh         Enciende y apaga la red y la página
└── web/
    ├── servidor.py             Servidor web y reglas del control
    ├── basedatos.py            Perfiles, pacientes y comandos de terminal
    ├── index.html              Panel completo: HTML, CSS y JavaScript
    ├── camilla.db              Base de datos; se crea sola y no se sube a git
    └── vendor/
        ├── bootstrap.min.css
        ├── bootstrap.bundle.min.js
        ├── fuentes.css
        └── fuentes/            Barlow Condensed, IBM Plex Mono, IBM Plex Sans y su licencia
```

`.gitignore` excluye `__pycache__/`, `*.pyc` y `web/camilla.db*`.

## 4. Requisitos

**Raspberry Pi**

| Elemento | Detalle |
|---|---|
| Equipo | Raspberry Pi 4 con interfaz WiFi `wlan0` |
| Sistema | Raspberry Pi OS con NetworkManager y systemd |
| Python | 3.8 o superior, solo biblioteca estándar. No requiere `pip`. |
| Red WiFi | `hostapd`, que se instala con `instalar_red.sh`. `encender_red.sh` usa además `dnsmasq`, `nft` y `nmcli`, ya presentes en el sistema. |
| Internet | Solo una vez, para instalar `hostapd` |

**Dispositivos de los usuarios:** un navegador web. No se instala nada.

**Computador de desarrollo:** Python 3. La parte web también funciona en Windows; los scripts de `red/` son exclusivos de Linux.

## 5. Instalación en la Raspberry Pi

Los comandos de esta guía usan la carpeta `~/Desktop/Proyecto Camilla`.

**Paso 1. Descargar el proyecto.**

```bash
cd ~/Desktop
git clone https://github.com/FisioterapiaCAP-123/ProyectoCamilla.git "Proyecto Camilla"
```

**Paso 2. Instalar la red WiFi.** Se ejecuta una sola vez y requiere internet.

```bash
cd ~/Desktop/"Proyecto Camilla"/red
sudo ./instalar_red.sh
```

El script instala `hostapd`, pide la clave de la red (mínimo 8 caracteres) y crea `/etc/hostapd/camilla.conf`, un archivo que solo `root` puede leer. Si la configuración ya existe, conserva la clave anterior.

**Paso 3. Encender el sistema.** Ver [Encender la red y la página](#61-encender-la-red-y-la-página). La base de datos `web/camilla.db` se crea sola la primera vez.

**Paso 4. Nombrar al primer administrador.** Se hace una sola vez.

1. Crear un perfil en la página con la opción "Crear perfil". Todo perfil nuevo entra como fisioterapeuta.
2. Ejecutar en la terminal:

   ```bash
   cd ~/Desktop/"Proyecto Camilla"
   python3 web/basedatos.py admin USUARIO
   ```

3. Si esa persona tenía la página abierta, debe salir y volver a entrar para ver las pestañas **Registros** y **Usuarios**.

La instalación no crea servicios: nada arranca solo al encender la Raspberry.

## 6. Operación

### 6.1 Encender la red y la página

```bash
cd ~/Desktop/"Proyecto Camilla"/red
./encender_red.sh
```

El script se ejecuta sin `sudo` delante y pide la contraseña de `sudo` solo para lo que la necesita. La página corre con el usuario normal. Al terminar de encender muestra la clave de la red y, desde ahí, quién se conecta, quién entra al panel, quién tiene el control y los paros de emergencia.

Para entrar, se conecta el celular a la red **Camilla**. La página se abre sola; si no ocurre, se escribe `http://10.42.0.1` en el navegador.

Mientras la red está encendida, la Raspberry se queda sin internet porque usa su única interfaz WiFi para crear la red.

### 6.2 Apagar la red y la página

Se presiona **ENTER** en la terminal del script. Esto apaga la red y la página, vuelve a conectar la Raspberry al WiFi anterior y agrega un reporte a `~/reporte_red.txt`.

Si la página ya estaba encendida antes de ejecutar el script, se reutiliza y sigue encendida al presionar ENTER.

### 6.3 Usar la página sin la red Camilla

```bash
cd ~/Desktop/"Proyecto Camilla"
python3 web/servidor.py
```

Se abre `http://localhost:8000` en la Raspberry o `http://IP-DE-LA-RASPBERRY:8000` desde otro equipo de la misma red. **Ctrl+C** apaga la página.

### 6.4 Ejecución en un computador de desarrollo

Desde la carpeta del proyecto, en Windows:

```powershell
python web\servidor.py
```

Se abre `http://localhost:8000`. Funcionan la interfaz, el inicio de sesión, los roles, la base de datos y la simulación. Para probar el control entre dos personas se usan dos pestañas con dos perfiles distintos. La red WiFi y el portal cautivo solo existen en la Raspberry.

El servidor crea `web/camilla.db` y `web/__pycache__/`, ambos ignorados por git.

Los cambios se llevan a la Raspberry con git. La carpeta no se debe copiar directamente desde Windows, porque los scripts `.sh` pueden quedar con fin de línea CRLF y dejan de ejecutarse en Linux.

### 6.5 Comandos de administración

Los comandos de `basedatos.py` se ejecutan desde la carpeta del proyecto.

| Tarea | Comando |
|---|---|
| Listar los perfiles y su rol | `python3 web/basedatos.py` |
| Hacer administrador a un perfil (también lo reactiva) | `python3 web/basedatos.py admin USUARIO` |
| Poner una contraseña nueva a un perfil | `python3 web/basedatos.py clave USUARIO` |
| Comprobar si la página está encendida | `ss -ltn 'sport = :8000'` (aparece `LISTEN` si lo está) |
| Ver los mensajes de la página en vivo, con la red encendida | `journalctl -t python3 -f` |
| Ver la clave del WiFi | `sudo grep wpa_passphrase /etc/hostapd/camilla.conf` |
| Cambiar la clave del WiFi (mínimo 8 caracteres) | `sudo nano /etc/hostapd/camilla.conf`, línea `wpa_passphrase=`. Aplica la próxima vez que se encienda la red. |

## 7. Funcionamiento

### 7.1 Perfiles e inicio de sesión

Cualquier persona puede crear su perfil desde "Crear perfil". El perfil entra como fisioterapeuta.

| Campo | Regla |
|---|---|
| Nombre (el que ven los demás) | De 2 a 40 letras, sin números, tildes, ñ, símbolos ni espacios |
| Usuario | De 3 a 20 letras o números, sin tildes, ñ, símbolos ni espacios. No distingue mayúsculas. |
| Contraseña | De 6 a 100 letras o números, sin tildes, ñ, símbolos ni espacios |

- Con datos incorrectos aparece "Usuario o contraseña incorrectos." y el servidor espera 1 s antes de contestar para frenar a quien intente adivinar.
- **Un perfil, una sesión.** Si se entra con el mismo usuario desde otro celular o pestaña, la sesión anterior se cierra y esa pantalla muestra "Tu sesión terminó".
- **La sesión es por pestaña.** Recargar la página la mantiene. Al cerrar la pestaña hay que volver a iniciar sesión.
- Una sesión sin uso durante 12 horas se borra.

### 7.2 Roles y permisos

| Función | Fisioterapeuta | Administrador |
|---|---|---|
| Usar la camilla, con las reglas del control | Sí | Sí |
| Paro de emergencia | Sí | Sí |
| Pestaña **Registros** (pacientes) | No | Sí |
| Pestaña **Usuarios** (perfiles) | No | Sí |

- El servidor verifica el rol en cada petición. Un fisioterapeuta que escriba las direcciones a mano recibe un rechazo.
- El primer administrador se nombra desde la terminal. Después, un administrador puede nombrar a otros desde la pestaña **Usuarios**.
- En **Usuarios**, cada perfil admite cambiar de rol, desactivar o activar, cambiar contraseña y borrar. El propio perfil no se puede modificar ahí, de modo que siempre queda al menos un administrador.
- Desactivar o borrar un perfil cierra su sesión al momento y, si tenía el control, lo libera.
- Un cambio de rol se refleja en la pantalla de esa persona en un segundo. Un cambio de contraseña no cierra su sesión abierta.
- Al borrar un perfil, los registros de pacientes que agregó se conservan.

### 7.3 Control de la camilla

El control pertenece a una persona (su perfil), no a un dispositivo. Quien lo tiene es el **titular** y su nombre aparece en todas las pantallas.

| Situación | Resultado |
|---|---|
| Se entra al panel y nadie tiene el control | Quien entra lo toma automáticamente. Esto incluye a los administradores. |
| Se entra al panel y otra persona lo tiene | Entra en solo lectura y la página ofrece "Solicitar el control". |
| Se solicita el control | El titular ve un aviso con **Permitir** y **No permitir** y tiene 30 s para decidir. Solo puede haber un pedido pendiente a la vez. |
| El titular no contesta | Cuenta como **no**: el control nunca se transfiere por silencio. |
| El titular libera o sale con un pedido pendiente | El control pasa directamente a quien lo pidió. |
| El titular deja de dar señales durante 10 s (cerró la página, bloqueó el celular o salió del WiFi) | El servidor libera el control. |
| El control cambia de persona | El servidor detiene los motores. |

**Bloquear**, arriba a la derecha, deshabilita los botones de movimiento solo en esa pantalla y no suelta el control. El paro de emergencia sigue disponible.

### 7.4 Movimiento

| Sección | Forma de mover | Recorrido | Lectura en pantalla |
|---|---|---|---|
| Altura | Mantener pulsado **Subir** o **Bajar** | Sin unidad | Barra aproximada, sin número |
| Cabeza | Un toque = 1°. Mantener pulsado repite. Campo "Ir a". | -30° a +70° | Ángulo en grados |
| Piernas | Un toque = 1°. Mantener pulsado repite. Campo "Ir a". | 0° a +45° | Ángulo en grados |

- **Plano 0°** lleva la cabeza y las piernas a 0°. La altura no cambia.
- La parte que se mueve se ilumina en el dibujo.
- Al llegar a un límite, el botón de esa dirección se deshabilita y aparece un aviso de tope.
- **Hombre muerto.** Mientras se mantiene pulsado un botón de altura, la página repite la orden cada 400 ms. Si la orden deja de llegar durante 1 s, el servidor detiene el motor sin esperar otra instrucción. El servidor revisa cada 0.5 s, así que la parada ocurre entre 1.0 y 1.5 s después de la última orden.
- La página detiene el movimiento manual al soltar el botón, al sacar el dedo del botón y al ocultarse la página. Al cambiar de pestaña del panel o perder la conexión, detiene además "Ir a" y "Plano 0°".

### 7.5 Paro de emergencia

- Lo puede activar cualquiera, tenga o no el control e incluso sin haber iniciado sesión, con el botón rojo (también presente en la pantalla de inicio de sesión) o con la tecla **Esc**. La tecla no actúa mientras se escribe en las pestañas o ventanas de administración.
- Es un único estado para todos: llega a todas las pantallas y bloquea el movimiento hasta que alguien lo libera.
- Al activarse, el servidor detiene el motor en marcha.
- Se libera con el mismo botón, que cambia a "Liberar". Liberarlo tampoco requiere iniciar sesión.
- Es un paro lógico que actúa sobre las órdenes del servidor. No existe un corte físico de la alimentación de los motores.

### 7.6 Simulación

- Las órdenes de movimiento se validan (solo el titular y sin paro activo) y se anotan en el registro, pero no accionan ningún motor.
- El servidor guarda los ángulos simulados de cabeza y piernas, de modo que todas las pantallas ven la misma posición.
- La altura no tiene sensor. Su barra y su dibujo son una estimación que cada pantalla calcula por su cuenta: no se comparte entre pantallas y no representa una altura real. Los avisos "En el tope superior" y "En el tope inferior" salen de esa estimación.

### 7.7 Registros de pacientes

- Cada registro tiene **paciente** (nombre, hasta 80 caracteres) y **edad** (de 0 a 120). También se guardan la fecha y el usuario que lo agregó.
- En la pestaña **Registros** el administrador agrega, busca, edita y borra. Borrar pide confirmación.

### 7.8 Pérdida de conexión

Si fallan 3 consultas seguidas al servidor, la página muestra **"Sin conexión con la camilla"**, detiene el movimiento y bloquea los botones. Al volver la comunicación, el aviso se cierra solo. El botón **Reintentar** fuerza una consulta inmediata.

## 8. Red WiFi Camilla

### 8.1 Configuración

| Parámetro | Valor |
|---|---|
| Nombre de la red | Camilla |
| Seguridad | WPA2 con clave compartida (WPA-PSK, CCMP) |
| Banda y canal | 2.4 GHz, canal 6 |
| Interfaz | `wlan0` |
| IP de la Raspberry | `10.42.0.1/24` |
| IP de los dispositivos | `10.42.0.10` a `10.42.0.254`, concesión de 60 minutos |
| Configuración | `/etc/hostapd/camilla.conf`, permiso 600 |

La red la crea `hostapd` y no NetworkManager porque, con el chip WiFi de la Raspberry Pi 4, NetworkManager agrega a la red opciones SHA256/WPA3 que el chip no maneja, y los celulares no se conectaban con clave.

### 8.2 Qué hace el encendido

`encender_red.sh` ejecuta estos pasos en orden:

1. Comprueba que exista la configuración de la red y que no se haya ejecutado con `sudo`. Avisa si todavía no hay administrador.
2. Pide la contraseña de `sudo` y anota el WiFi activo para volver a él al final.
3. Saca `wlan0` del manejo de NetworkManager y le asigna la dirección `10.42.0.1/24`.
4. Arranca `hostapd` y comprueba que la red quedó activa. Si falla, muestra los últimos mensajes de `hostapd` y revierte los cambios.
5. Arranca `dnsmasq`, que entrega las direcciones IP y responde que cualquier sitio de internet está en la Raspberry.
6. Crea la tabla `camilla` de `nft`, que pasa el puerto 80 al 8000.
7. Arranca `web/servidor.py` con el usuario normal. Si el puerto 8000 ya está ocupado, usa la página que ya estaba encendida.
8. Muestra los datos de la red y un monitor de eventos. Cada 15 s indica cuántos dispositivos hay conectados.

### 8.3 Qué hace el apagado

Al presionar ENTER o al interrumpirse el script:

1. Guarda en el reporte los dispositivos conectados en ese momento.
2. Detiene la página, si la arrancó el script, y el monitor de eventos.
3. Detiene `hostapd` y `dnsmasq`.
4. Borra la tabla `camilla` de `nft`.
5. Quita la dirección de `wlan0` y la devuelve a NetworkManager.
6. Vuelve a conectar al WiFi anterior.
7. Agrega al reporte los mensajes del sistema generados durante la sesión.

### 8.4 Portal cautivo

El portal cautivo es lo que hace que la página se abra sola al conectarse, como en el WiFi de un hotel:

1. Al conectarse, el celular consulta sitios como `captive.apple.com` para saber si hay internet.
2. `dnsmasq` responde que ese sitio está en `10.42.0.1`.
3. La regla de `nft` lleva la consulta del puerto 80 al servidor, en el puerto 8000.
4. El servidor detecta que la petición pide otro sitio y responde con una redirección a `http://10.42.0.1:8000/`.
5. El celular muestra la página.

### 8.5 Reporte de pruebas

Cada apagado agrega a `~/reporte_red.txt` la hora de inicio, la red anterior, los dispositivos conectados al final y los mensajes de `hostapd`, `dnsmasq`, `dnsmasq-dhcp`, `kernel` y `python3`.

## 9. Datos y seguridad

| Tema | Implementación |
|---|---|
| Contraseñas | Se guardan como resumen criptográfico (PBKDF2-HMAC-SHA256, 300 000 iteraciones, sal aleatoria por perfil), nunca en texto. |
| Sesiones | Token aleatorio guardado en la memoria del servidor. La página lo conserva en `sessionStorage` y lo envía en cada petición. |
| Autorización | El servidor revisa la sesión, el titular, el paro y el rol en cada petición. Lo que deshabilita la página es solo presentación. |
| Base de datos | `web/camilla.db`, con permiso 600 en Linux: solo la lee el usuario de la Raspberry. No se sube a git. |
| Datos de pacientes | Solo están en `web/camilla.db`. En el registro de actividad queda el número del registro, nunca el nombre. |
| Archivos servidos | Solo los de una lista fija. Cualquier otra ruta responde 404. |

**Registro de actividad.** El servidor anota sesiones, cambios de control, paros y acciones de administración. Los mensajes salen por la terminal o, con la red encendida, por el registro del sistema con la etiqueta `python3`. Estos eventos no se guardan en la base de datos.

**Limitaciones de seguridad de esta versión.**

- La página va por HTTP sin cifrar: el tráfico, incluidas contraseñas y datos de pacientes, viaja sin protección para quien tenga la clave del WiFi. Es aceptable para pruebas; antes de usarla con pacientes reales hay que resolverlo.
- El registro de perfiles está abierto: quien tenga acceso a la red puede crear un perfil de fisioterapeuta y operar la camilla.
- El paro de emergencia se puede liberar sin iniciar sesión.

La lista completa está en [INTEGRACION.md](INTEGRACION.md#11-comportamientos-a-tener-en-cuenta).

## 10. Mantenimiento

**Aplicar cambios.**

| Archivo modificado | Qué hacer |
|---|---|
| `web/index.html` | Guardar y recargar la página en el navegador. No hace falta reiniciar. |
| `web/servidor.py` | Reiniciar la página: ENTER y otra vez `./encender_red.sh`, o **Ctrl+C** y otra vez `python3 web/servidor.py`. |
| `web/basedatos.py` | Igual que `web/servidor.py`. |
| Roles o contraseñas desde la terminal | No hay que reiniciar. Quien tenga la página abierta debe salir y volver a entrar para ver su rol nuevo. |

- Los archivos de la página se leen cada vez que alguien la abre.
- `web/servidor.py` solo se lee al arrancar. Al reiniciarlo se pierden las sesiones y el control.
- Los valores ajustables (tiempos y límites) están descritos en [Parámetros](INTEGRACION.md#7-parámetros).

## 11. Solución de problemas

**Mensajes del sistema**

| Mensaje | Causa | Solución |
|---|---|---|
| `Primero instala la red con: sudo ./instalar_red.sh` | No existe la configuración de la red | Ejecutar `sudo ./instalar_red.sh` |
| `Correlo sin sudo: ./encender_red.sh` | El script se ejecutó con `sudo` delante | Ejecutarlo sin `sudo` |
| `No se pudo encender la red` | `hostapd` no arrancó | Revisar los mensajes que muestra el script a continuación |
| `Aviso: no hay administrador` | Ningún perfil activo es administrador | Crear un perfil y ejecutar `python3 web/basedatos.py admin USUARIO` |
| "Tu sesión terminó" | Se entró desde otro dispositivo, el servidor se reinició o el perfil se desactivó | Volver a iniciar sesión |
| "Tu perfil está desactivado" | Un administrador lo desactivó | Un administrador debe activarlo en **Usuarios** |
| "Sin conexión con la camilla" | La página no recibe respuesta del servidor | Revisar el WiFi y que la página siga encendida |
| Contraseña olvidada | | `python3 web/basedatos.py clave USUARIO` |

**Celulares y navegadores**

| Síntoma | Solución |
|---|---|
| Xiaomi o Android se desconecta "por no tener internet" | Apagar el cambio automático a datos móviles (Ajustes → Wi-Fi → Asistente de Wi-Fi) y elegir mantener la conexión. |
| iPhone pregunta al cerrar la ventana de la página | Elegir **"Usar sin Internet"**. |
| En Android, "Usar esta red como está" cierra la ventana de la página | Usar la página dentro de esa ventana sin tocar el menú, o abrir `http://10.42.0.1` en el navegador con los datos móviles apagados. |
| Se pierde el control al bloquear el celular | Es intencional. La página deja de dar señales y el control se libera a los 10 s para que la camilla no quede tomada por una pantalla apagada. |
| La página no carga al escribir la dirección | Escribir `http://` al inicio. Sin eso, algunos navegadores intentan `https`. |
| Sigue saliendo la versión vieja después de recargar | Es la caché del navegador. Cerrar la pestaña y abrirla de nuevo. |

**Recuperar el internet si la terminal se cerró con la red encendida**

```bash
pkill -f web/servidor.py
sudo pkill -F /run/camilla-hostapd.pid
sudo pkill -F /run/camilla-dnsmasq.pid
sudo nft destroy table ip camilla
sudo ip addr flush dev wlan0
nmcli device set wlan0 managed yes
```

## 12. Desinstalación

Cada componente se puede retirar por separado. Antes de empezar se apagan la red y la página con ENTER o **Ctrl+C**.

**Red WiFi Camilla**

```bash
sudo rm -f /etc/hostapd/camilla.conf
sudo apt purge hostapd
```

Después de esto `encender_red.sh` deja de funcionar. La página se puede seguir abriendo con `python3 web/servidor.py`.

**Reporte de pruebas**

```bash
rm -f ~/reporte_red.txt
```

**Perfiles y registros de pacientes**

> **Advertencia:** esta acción borra de forma permanente todos los perfiles y registros de pacientes. La base de datos se vuelve a crear vacía al encender la página.

```bash
rm -f ~/Desktop/"Proyecto Camilla"/web/camilla.db*
```

**Proyecto completo**

> **Advertencia:** esta acción borra de forma permanente la carpeta del proyecto, incluida la base de datos con los perfiles y registros de pacientes.

```bash
rm -rf ~/Desktop/"Proyecto Camilla"
```

El proyecto no crea servicios de systemd, reglas de `sudo` o polkit ni tareas programadas, por lo que no hay nada más que retirar.

En un computador de desarrollo no se instala nada en el sistema: basta con borrar la carpeta del proyecto.

## 13. Cambios en el sistema operativo

Cambios hechos en la Raspberry fuera de la carpeta del proyecto, según la última revisión registrada (05-11-2026).

**Permanentes**

| Elemento | Ubicación | Cómo deshacer |
|---|---|---|
| Paquete `hostapd`. Su servicio de Debian está `masked` y nunca arranca solo. | Paquete del sistema (`apt`) | `sudo apt purge hostapd` |
| Configuración de la red, incluida la clave | `/etc/hostapd/camilla.conf` | `sudo rm -f /etc/hostapd/camilla.conf` |
| Reporte de pruebas; crece con cada prueba | `~/reporte_red.txt` | `rm -f ~/reporte_red.txt` |

**Solo mientras la red está encendida.** El script los retira al apagar: `wlan0` fuera de NetworkManager, la IP `10.42.0.1`, los procesos `hostapd` y `dnsmasq`, la tabla `camilla` de `nft` y la página. Los archivos de PID y de concesiones están en `/run`.

- Nada arranca solo al encender la Raspberry. La red y la página se encienden a mano con `encender_red.sh`.
- No hay servicios de systemd del proyecto, reglas de `sudo` o polkit ni tareas programadas.
- El panel (29-10-2026) y los perfiles con roles (05-11-2026) no cambiaron nada del sistema: todo está dentro de la carpeta del proyecto.
- No se instaló nada más ni se cambió la red "Meso".

**Historial**

| Fecha | Cambio | Ubicación | Estado |
|---|---|---|---|
| 21-10-2026 | Servicio que arrancaba la página al encender | `~/.config/systemd/user/camilla-web.service` | Quitado el 28-10-2026 |
| 21-10-2026 | "Linger": el servicio arrancaba sin iniciar sesión | `/var/lib/systemd/linger/diegocardona` | Quitado el 28-10-2026 |
| 21-10-2026 | Programa `hostapd` | Paquete del sistema (`apt`) | Instalado |
| 21-10-2026 | Configuración de la red | `/etc/hostapd/camilla.conf` | Activo |
| 21-10-2026 | Reporte de pruebas de la red | `~/reporte_red.txt` | Activo |
| 21-10-2026 | Perfil "Camilla" de NetworkManager | `/etc/NetworkManager/system-connections/` | Borrado (no funcionaba) |

## 14. Glosario

| Término | Significado |
|---|---|
| Titular | Persona que tiene el control de la camilla en ese momento. |
| Solo lectura | Estado de una pantalla que ve la camilla sin poder moverla. |
| Hombre muerto | Mecanismo por el cual un motor solo sigue en marcha mientras llega la señal de que el botón está pulsado. |
| Paro de emergencia | Estado único del sistema que bloquea todo movimiento hasta que se libera. |
| Telemetría | Posición de la camilla que el servidor informa a las pantallas. |
| Final de carrera | Interruptor que indica que una pieza llegó a su tope. Hoy no hay ninguno conectado. |
| Portal cautivo | Página que el celular abre solo al conectarse a una red, como en el WiFi de un hotel. |
| Token de sesión | Código aleatorio que identifica a una persona con sesión iniciada. |
| PBKDF2 | Método que convierte una contraseña en un valor del que no se puede recuperar el original. |
