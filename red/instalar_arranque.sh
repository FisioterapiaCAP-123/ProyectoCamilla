#!/bin/bash
# Arranque automatico: al encender la Raspberry se encienden solas la red WiFi
# "Camilla" y la pagina, sin iniciar sesion ni escribir claves.
# Si alguna se cae, systemd la vuelve a encender en unos segundos.
#
#   sudo ./instalar_arranque.sh           instala y deja activado el arranque automatico
#   sudo ./instalar_arranque.sh quitar    lo desactiva y vuelve todo a internet
#
# Antes, una sola vez y con internet:  sudo ./instalar_red.sh
# Despues de instalar no se usa encender_red.sh: la red y la pagina ya corren solas.

set -e
if [ "$(id -u)" -ne 0 ]; then
    echo "Ejecutalo con sudo:  sudo ./instalar_arranque.sh"
    exit 1
fi

USUARIO="${SUDO_USER:-}"
if [ -z "$USUARIO" ] || [ "$USUARIO" = "root" ]; then
    echo "Ejecutalo con sudo desde tu usuario (no como root directo): la pagina corre con tu usuario."
    exit 1
fi
PROYECTO=$(dirname "$(dirname "$(readlink -f "$0")")")  # carpeta del proyecto
UNIDADES=/etc/systemd/system

if [ "$1" = "quitar" ]; then
    systemctl disable --now camilla-pagina.service camilla-red.service 2>/dev/null || true
    rm -f "$UNIDADES/camilla-pagina.service" "$UNIDADES/camilla-red.service" /usr/local/sbin/camilla-red
    systemctl daemon-reload
    echo "Listo: ya no arranca sola. La Raspberry vuelve a conectarse a internet."
    echo "Para encender a mano, como antes:  ./encender_red.sh"
    exit 0
fi

[ -e /etc/hostapd/camilla.conf ] || { echo "Primero instala la red con:  sudo ./instalar_red.sh"; exit 1; }

# El script de la red se copia a una ruta sin espacios (la carpeta del proyecto puede tenerlos)
install -m 755 "$PROYECTO/red/arranque_red.sh" /usr/local/sbin/camilla-red

cat > "$UNIDADES/camilla-red.service" <<EOF
[Unit]
Description=Red WiFi Camilla (hostapd y dnsmasq)
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
ExecStart=/usr/local/sbin/camilla-red iniciar
ExecStopPost=/usr/local/sbin/camilla-red apagar
Restart=on-failure
RestartSec=5
SyslogIdentifier=hostapd

[Install]
WantedBy=multi-user.target
EOF

# La pagina corre con el usuario normal, nunca como root. Sus mensajes van al registro
# como "python3", igual que con encender_red.sh
cat > "$UNIDADES/camilla-pagina.service" <<EOF
[Unit]
Description=Pagina de la camilla (web/servidor.py)
After=camilla-red.service
Wants=camilla-red.service

[Service]
Type=simple
User=$USUARIO
SupplementaryGroups=dialout
WorkingDirectory=$PROYECTO/web
ExecStart=/usr/bin/python3 -u servidor.py
Restart=always
RestartSec=3
SyslogIdentifier=python3

[Install]
WantedBy=multi-user.target
EOF

usermod -aG dialout "$USUARIO"  # permiso para hablar con el ESP32 por USB
systemctl daemon-reload
systemctl enable camilla-red.service camilla-pagina.service

sudo -u "$USUARIO" python3 "$PROYECTO/web/basedatos.py" revisar  # avisa si falta administrador

echo
echo "Listo: la red Camilla y la pagina se encenderan solas al prender la Raspberry."
echo "No se encendieron ahora para no cortar internet ni una conexion SSH por WiFi."
echo
echo "  Para probar:  sudo reboot"
echo "  Ver estado:   systemctl status camilla-red camilla-pagina"
echo "  Quitarlo:     sudo ./instalar_arranque.sh quitar"
