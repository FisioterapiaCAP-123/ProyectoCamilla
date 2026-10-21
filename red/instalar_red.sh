#!/bin/bash
# Instala hostapd y crea la configuracion de la red WiFi "Camilla" (WPA2 normal).
# Se corre una sola vez, con internet:  sudo ./instalar_red.sh
#
# Se usa hostapd porque NetworkManager le agrega a la red WPA2 opciones extra
# (SHA256 / WPA3) que el chip WiFi de la Raspberry Pi 4 no maneja bien, y los
# celulares no se pueden conectar con clave.

set -e
if [ "$(id -u)" -ne 0 ]; then
    echo "Ejecutalo con sudo:  sudo ./instalar_red.sh"
    exit 1
fi

apt-get install -y hostapd

# Misma clave de antes si ya estaba instalada; si no, se pide una nueva
CLAVE=$(sed -n 's/^wpa_passphrase=//p' /etc/hostapd/camilla.conf 2>/dev/null || true)
while [ ${#CLAVE} -lt 8 ]; do
    read -r -p "Clave para la red Camilla (minimo 8 caracteres): " CLAVE
done

CONF=/etc/hostapd/camilla.conf
install -m 600 /dev/null "$CONF"  # solo root puede leerlo (tiene la clave)
cat > "$CONF" <<EOF
interface=wlan0
driver=nl80211
ctrl_interface=/run/hostapd
ctrl_interface_group=netdev
ssid=Camilla
country_code=GT
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
ieee80211w=0
wpa_passphrase=$CLAVE
logger_stdout=-1
logger_stdout_level=1
EOF

echo
echo "Listo. Para encender la red:  ./encender_red.sh"
