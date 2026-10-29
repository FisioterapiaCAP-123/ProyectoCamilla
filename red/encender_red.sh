#!/bin/bash
# Enciende la red WiFi "Camilla" de la Raspberry (con hostapd) y la pagina web
# (web/servidor.py), y muestra en vivo quien se conecta. Al presionar ENTER apaga
# las dos y vuelve a conectar a internet.
#
# Uso:  ./encender_red.sh      (sin sudo delante: pide la clave de sudo al empezar)
# Antes hay que instalar una sola vez:  sudo ./instalar_red.sh
#
# Cada prueba se agrega al reporte ~/reporte_red.txt

CONF=/etc/hostapd/camilla.conf
CTRL=/run/hostapd
REPORTE="$HOME/reporte_red.txt"
INICIO=$(date '+%Y-%m-%d %H:%M:%S')
PROYECTO=$(dirname "$(dirname "$(readlink -f "$0")")")  # carpeta "Proyecto Camilla"

[ -e "$CONF" ] || { echo "Primero instala la red con:  sudo ./instalar_red.sh"; exit 1; }
# Con sudo delante la pagina correria como root: el script pide la clave solo para lo que la necesita
[ "$(id -u)" -ne 0 ] || { echo "Correlo sin sudo:  ./encender_red.sh"; exit 1; }
sudo -v || exit 1

# WiFi al que hay que volver al terminar (p. ej. "Meso")
ANTERIOR=$(nmcli -t -f NAME,TYPE con show --active | awk -F: '$2 == "802-11-wireless" {print $1; exit}')

apagar() {
    trap - INT TERM HUP
    echo
    {
        echo "===== $INICIO  red=Camilla (hostapd)  anterior=${ANTERIOR:-ninguna} ====="
        echo "--- dispositivos conectados al final"; hostapd_cli -p $CTRL -i wlan0 all_sta 2>&1
    } >> "$REPORTE"
    echo "Apagando la red Camilla y la pagina..."
    pkill -P $$ 2>/dev/null  # detener la pagina y el monitor de eventos
    sudo pkill -F /run/camilla-hostapd.pid 2>/dev/null
    sudo pkill -F /run/camilla-dnsmasq.pid 2>/dev/null
    sudo nft destroy table ip camilla 2>/dev/null
    sudo ip addr flush dev wlan0
    nmcli device set wlan0 managed yes  # NetworkManager vuelve a manejar el WiFi
    if [ -n "$ANTERIOR" ]; then
        echo "Volviendo a conectar a $ANTERIOR..."
        sleep 2
        nmcli con up "$ANTERIOR" >/dev/null 2>&1 && echo "Listo: conectado a $ANTERIOR" \
            || echo "No se pudo conectar a $ANTERIOR, conectate desde el icono de WiFi"
    fi
    journalctl --since "$INICIO" --no-pager -o short -t hostapd -t dnsmasq -t dnsmasq-dhcp \
        -t kernel -t python3 >> "$REPORTE" 2>&1
    echo "Reporte guardado en $REPORTE"
    exit
}
trap apagar INT TERM HUP

echo "Encendiendo la red Camilla (la Raspberry se queda sin internet)..."
nmcli device set wlan0 managed no  # NetworkManager suelta el WiFi para hostapd
sleep 2
sudo ip addr flush dev wlan0
sudo ip addr add 10.42.0.1/24 dev wlan0

# hostapd crea la red; sus mensajes van al registro del sistema como "hostapd"
sudo stdbuf -oL hostapd -P /run/camilla-hostapd.pid "$CONF" 2>&1 | logger -t hostapd &
sleep 3
if ! hostapd_cli -p $CTRL -i wlan0 status 2>/dev/null | grep -q "state=ENABLED"; then
    echo "No se pudo encender la red. Ultimos mensajes de hostapd:"
    journalctl -t hostapd --since "$INICIO" -o cat --no-pager | tail -n 15
    apagar
fi

# DHCP y DNS: le da una IP (10.42.0.x) a cada dispositivo y responde que cualquier
# sitio (captive.apple.com, google.com...) esta en la Raspberry
sudo dnsmasq --conf-file=/dev/null --no-hosts --no-resolv --bind-interfaces --except-interface=lo \
    --listen-address=10.42.0.1 --dhcp-range=10.42.0.10,10.42.0.254,60m --address=/#/10.42.0.1 \
    --dhcp-leasefile=/run/camilla-dnsmasq.leases --pid-file=/run/camilla-dnsmasq.pid

# Las comprobaciones de internet de los celulares usan el puerto 80: se pasan al servidor (8000)
sudo nft destroy table ip camilla 2>/dev/null
sudo nft -f - <<'EOF'
table ip camilla {
    chain prerouting {
        type nat hook prerouting priority dstnat;
        iifname "wlan0" tcp dport 80 redirect to :8000
    }
}
EOF

# Pagina web (puerto 8000): corre con tu usuario, sin sudo. Sus mensajes van al registro como "python3"
if ss -ltn 'sport = :8000' | grep -q LISTEN; then
    echo "La pagina ya estaba encendida (puerto 8000 ocupado): se usa esa."
else
    python3 -u "$PROYECTO/web/servidor.py" 2>&1 | logger -t python3 &
fi

echo
echo "  Red WiFi:  Camilla"
echo "  Clave:     $(sudo sed -n 's/^wpa_passphrase=//p' "$CONF")"
echo "  Pagina:    se abre sola al conectarse (o entra a http://10.42.0.1)"
echo
echo "Busca la red en el celular. Aqui veras si alguien se conecta."
echo "Presiona ENTER para apagar la red y la pagina y volver a internet."
echo

# Monitor de eventos: conexiones, clave incorrecta, IP entregada y visitas a la pagina
journalctl -f -n 0 -o cat -t hostapd -t dnsmasq-dhcp -t python3 2>/dev/null |
while read -r linea; do
    case "$linea" in
        *AP-STA-CONNECTED*)    echo "  >> Se conecto un dispositivo (${linea##* })" ;;
        *AP-STA-DISCONNECTED*) echo "  >> Se desconecto un dispositivo (${linea##* })" ;;
        *PSK-MISMATCH*)        echo "  >> Alguien intento conectarse con la CLAVE INCORRECTA" ;;
        DHCPACK*)              echo "  >> IP entregada: ${linea#* }" ;;
        *'"GET / '*)           echo "  >> Alguien abrio la pagina desde ${linea%% *}" ;;
    esac
done &

while true; do
    read -r -t 15; [ $? -le 128 ] && break  # ENTER: salir; si no, sigue cada 15 s
    sudo -n -v 2>/dev/null  # mantener activa la clave de sudo para poder apagar
    n=$(hostapd_cli -p $CTRL -i wlan0 all_sta 2>/dev/null | grep -cE '^([0-9a-f]{2}:){5}[0-9a-f]{2}$')
    echo "  $(date +%H:%M:%S)  red encendida - dispositivos conectados: $n"
done
apagar
