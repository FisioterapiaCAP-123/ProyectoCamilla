#!/bin/bash
# Red WiFi "Camilla" para el arranque automatico. NO se corre a mano:
# lo usa el servicio camilla-red (systemd, como root, sin pedir clave).
# Hace lo mismo que encender_red.sh, pero sin monitor ni ENTER.
#
#   arranque_red.sh iniciar   prepara wlan0, enciende dnsmasq y deja hostapd corriendo
#   arranque_red.sh apagar    deshace todo y le devuelve el WiFi a NetworkManager
#
# Si hostapd se cae, el servicio termina y systemd lo vuelve a encender solo.
# Se instala con:  sudo ./instalar_arranque.sh

CONF=/etc/hostapd/camilla.conf
IP=10.42.0.1

iniciar() {
    [ -e "$CONF" ] || { echo "Falta $CONF: primero  sudo ./instalar_red.sh"; exit 1; }

    # Al encender, el WiFi puede tardar unos segundos en aparecer
    for _ in $(seq 1 30); do
        [ -e /sys/class/net/wlan0 ] && break
        sleep 1
    done
    [ -e /sys/class/net/wlan0 ] || { echo "No aparecio wlan0"; exit 1; }

    rfkill unblock wlan 2>/dev/null
    nmcli device set wlan0 managed no 2>/dev/null  # NetworkManager suelta el WiFi para hostapd
    sleep 2
    ip addr flush dev wlan0
    ip addr add $IP/24 dev wlan0

    # Las comprobaciones de internet de los celulares usan el puerto 80: se pasan a la pagina (8000)
    nft destroy table ip camilla 2>/dev/null
    nft -f - <<'EOF'
table ip camilla {
    chain prerouting {
        type nat hook prerouting priority dstnat;
        iifname "wlan0" tcp dport 80 redirect to :8000
    }
}
EOF

    # DHCP y DNS: una IP 10.42.0.x a cada dispositivo, y cualquier sitio responde la Raspberry.
    # Queda dentro del servicio: systemd lo apaga junto con hostapd.
    dnsmasq --keep-in-foreground --conf-file=/dev/null --no-hosts --no-resolv --bind-interfaces \
        --except-interface=lo --listen-address=$IP --dhcp-range=10.42.0.10,10.42.0.254,60m \
        --address=/#/$IP --dhcp-leasefile=/run/camilla-dnsmasq.leases &

    # hostapd crea la red y queda como proceso principal del servicio
    exec hostapd "$CONF"
}

apagar() {
    nft destroy table ip camilla 2>/dev/null
    ip addr flush dev wlan0 2>/dev/null
    nmcli device set wlan0 managed yes 2>/dev/null  # el WiFi vuelve a NetworkManager (internet)
}

case "$1" in
    iniciar) iniciar ;;
    apagar)  apagar ;;
    *) echo "Uso: $0 iniciar|apagar  (lo usa el servicio camilla-red)"; exit 1 ;;
esac
