"""Prueba del motor paso a paso (DRV8825) para la altura de la camilla (MicroPython).

NO es el programa de la camilla: se abre en Thonny y se corre con F5 (no se guarda
como main.py). Se escribe en la consola de Thonny y se presiona Enter:

    s          subir hasta dar otra orden (o hasta que pasen TIEMPO_MAXIMO_S)
    b          bajar
    s 400      subir exactamente 400 pasos (b 400 para bajar)
    p          parar (o Enter con la linea vacia)
    v 600      cambiar la velocidad a 600 pasos por segundo
    0          poner el contador de posicion en 0
    ?          ver posicion y configuracion

Al parar dice cuantos pasos dio: sirve para medir el recorrido de tope a tope.
El boton Stop de Thonny (o Ctrl+C) para el motor y lo deja suelto.

Conexion ESP32 -> DRV8825:
    GPIO 25 -> STEP
    GPIO 33 -> DIR
    GPIO 13 -> EN        (activo en bajo: 0 = motor con fuerza, 1 = suelto)
    3.3 V   -> RST y SLP (los dos juntos)
    GND     -> GND del driver, comun con el GND de la fuente del motor
    Fuente del motor -> VMOT y GND, con un capacitor de 100 uF cerca del driver
                        (la fuente va SOLO al driver: nunca al motor ni al ESP32)
    M0, M1, M2 -> micropasos (sin conectar = paso completo; poner MICROPASOS igual)
Conexion DRV8825 -> motor NEMA 17 (4 cables, 2 bobinas):
    1A, 2A -> bobina A      1B, 2B -> bobina B   (en otras placas: A1, A2, B1, B2)
    En la placa morada, STEP se llama STP.
    Para saber cuales son pareja: con el multimetro en continuidad, los 2 cables
    que suenan son una bobina (o, al juntarlos, el eje cuesta girarlo a mano).
    Si gira al reves no se cambian cables: se cambia SUBIR_CON_DIR.
Corriente del driver = Vref x 2 (Vref se mide entre el potenciometro y GND).
Finales de carrera (opcionales, USAR_FINALES = True), normalmente abiertos, a GND:
    GPIO 4  -> abajo   (usa la resistencia interna del ESP32)
    GPIO 35 -> arriba  (solo entrada: necesita una resistencia de 10 kohm a 3.3 V)

Nunca conectar o desconectar el motor con la fuente encendida: se quema el driver.
"""
import math
import select
import sys
import time

from machine import Pin

# ---------- CONFIGURACION ----------
PIN_STEP = 25
PIN_DIR = 33
PIN_EN = 13
PIN_FINAL_ABAJO = 4
PIN_FINAL_ARRIBA = 35
USAR_FINALES = False        # True cuando esten conectados los finales de carrera
SUBIR_CON_DIR = 1           # si "s" baja en vez de subir, cambiar a 0
MICROPASOS = 1              # 1, 2, 4, 8, 16 o 32 segun M0-M2 (solo para mostrar vueltas)
PASOS_POR_VUELTA = 200      # motor de 1.8 grados por paso
VELOCIDAD = 400             # pasos por segundo, maxima
VELOCIDAD_INICIO = 100      # arranca despacio para no saltarse pasos con carga
ACELERACION = 800           # pasos por segundo, cada segundo (rampa)
TIEMPO_MAXIMO_S = 15        # sin otra orden, se detiene solo despues de este tiempo
MANTENER_FUERZA = True      # al parar el motor sigue sujetando (se calienta); False lo suelta
PAUSA_CAMBIO_MS = 300       # pausa antes de invertir el sentido
ANCHO_PULSO_US = 5          # el DRV8825 necesita al menos 2 us en alto
REVISAR_CADA_MS = 20        # cada cuanto se lee la consola mientras se mueve
# -----------------------------------

step = Pin(PIN_STEP, Pin.OUT, value=0)
direccion = Pin(PIN_DIR, Pin.OUT, value=0)
habilitar = Pin(PIN_EN, Pin.OUT, value=1)       # empieza suelto
led = Pin(2, Pin.OUT, value=0)
final_abajo = Pin(PIN_FINAL_ABAJO, Pin.IN, Pin.PULL_UP)
final_arriba = Pin(PIN_FINAL_ARRIBA, Pin.IN)    # GPIO 35 no tiene resistencia interna

posicion = 0                # pasos desde el ultimo 0 (+ arriba, - abajo)
velocidad_max = VELOCIDAD


class Consola:
    """Lee lineas de la consola de Thonny sin detener el motor mientras espera."""

    def __init__(self):
        self.entrada = select.poll()
        self.entrada.register(sys.stdin, select.POLLIN)
        self.lector = getattr(sys.stdin, "buffer", sys.stdin)
        self.texto = ""

    def linea(self):
        """Devuelve una linea completa si ya se presiono Enter; si no, None."""
        while self.entrada.poll(0):
            dato = self.lector.read(1)
            if not dato:
                break
            codigo = dato[0] if isinstance(dato, bytes) else ord(dato)
            if codigo == 10:
                listo, self.texto = self.texto.strip(), ""
                return listo
            if codigo != 13 and len(self.texto) < 40:
                self.texto += chr(codigo)
        return None


def en_tope(sentido):
    """True si el final de carrera hacia ese sentido esta presionado (0 = presionado)."""
    if not USAR_FINALES:
        return False
    return (final_arriba if sentido > 0 else final_abajo).value() == 0


def soltar():
    step.value(0)
    habilitar.value(1)
    led.value(0)


def vueltas(pasos):
    return pasos / (PASOS_POR_VUELTA * MICROPASOS)


def mover(sentido, consola, pasos=None):
    """Mueve hasta llegar a los pasos, a un tope, al tiempo maximo o a otra orden.
    Devuelve la orden que interrumpio el movimiento (o None)."""
    global posicion
    nombre = "arriba" if sentido > 0 else "abajo"
    if en_tope(sentido):
        print("No se mueve: el final de carrera de %s esta presionado." % nombre)
        return None

    direccion.value(SUBIR_CON_DIR if sentido > 0 else 1 - SUBIR_CON_DIR)
    habilitar.value(0)
    led.value(1)
    time.sleep_ms(2)        # el driver necesita un momento tras cambiar DIR o EN

    print("Moviendo hacia %s... (Enter para parar)" % nombre)
    dados = 0
    vel = float(min(VELOCIDAD_INICIO, velocidad_max))
    inicio = time.ticks_ms()
    revisado = inicio
    proximo = time.ticks_us()
    orden = None
    motivo = "orden"
    while True:
        espera = time.ticks_diff(proximo, time.ticks_us())
        if espera > 0:
            time.sleep_us(espera)
        elif espera < -5000:            # se atraso mucho: no recuperar de golpe
            proximo = time.ticks_us()

        step.value(1)
        time.sleep_us(ANCHO_PULSO_US)
        step.value(0)
        dados += 1
        posicion += sentido

        if pasos is not None and dados >= pasos:
            motivo = "llego a %d pasos" % pasos
            break
        if en_tope(sentido):
            motivo = "final de carrera de %s" % nombre
            break

        # Rampa: acelera al arrancar y, con pasos fijos, frena antes de llegar
        vel = min(velocidad_max, math.sqrt(vel * vel + 2 * ACELERACION))
        if pasos is not None:
            frenado = math.sqrt(VELOCIDAD_INICIO * VELOCIDAD_INICIO + 2 * ACELERACION * (pasos - dados))
            vel = min(vel, frenado)
        proximo = time.ticks_add(proximo, int(1000000 / vel))

        ahora = time.ticks_ms()
        if time.ticks_diff(ahora, revisado) >= REVISAR_CADA_MS:
            revisado = ahora
            orden = consola.linea()
            if orden is not None:
                break
            if time.ticks_diff(ahora, inicio) >= TIEMPO_MAXIMO_S * 1000:
                motivo = "tiempo maximo (%d s)" % TIEMPO_MAXIMO_S
                break

    if MANTENER_FUERZA:
        led.value(0)
    else:
        soltar()
    segundos = time.ticks_diff(time.ticks_ms(), inicio) / 1000
    print("Parado (%s). Pasos: %d (%.2f vueltas) en %.1f s. Posicion: %d"
          % (motivo, dados, vueltas(dados), segundos, posicion))
    return orden


def ayuda():
    print("Ordenes: s | b | s 400 | b 400 | p | v 600 | 0 | ?   (y Enter)")


def mostrar_estado():
    print("Posicion: %d pasos (%.2f vueltas). Velocidad: %d pasos/s. Micropasos: 1/%d."
          % (posicion, vueltas(posicion), velocidad_max, MICROPASOS))
    if USAR_FINALES:
        print("Final abajo: %s. Final arriba: %s." % (
            "presionado" if final_abajo.value() == 0 else "libre",
            "presionado" if final_arriba.value() == 0 else "libre"))
    else:
        print("Finales de carrera: desactivados (USAR_FINALES = False).")


def atender(orden, consola):
    """Ejecuta una orden. Si un movimiento fue interrumpido por otra orden, la devuelve."""
    global posicion, velocidad_max
    partes = orden.lower().split()
    if not partes or partes[0] == "p":
        return None
    letra = partes[0]
    if letra in ("s", "b"):
        pasos = None
        if len(partes) > 1:
            if not partes[1].isdigit() or int(partes[1]) == 0:
                print("Los pasos deben ser un numero mayor que 0, por ejemplo: s 400")
                return None
            pasos = int(partes[1])
        siguiente = mover(1 if letra == "s" else -1, consola, pasos)
        if siguiente:
            time.sleep_ms(PAUSA_CAMBIO_MS)
        return siguiente
    if letra == "v" and len(partes) > 1 and partes[1].isdigit():
        velocidad_max = max(VELOCIDAD_INICIO, min(5000, int(partes[1])))
        print("Velocidad maxima: %d pasos/s" % velocidad_max)
    elif letra == "0":
        posicion = 0
        print("Contador en 0.")
    elif letra == "?":
        mostrar_estado()
    else:
        ayuda()
    return None


def arrancar():
    consola = Consola()
    print("# prueba del stepper lista")
    ayuda()
    mostrar_estado()
    try:
        while True:
            orden = consola.linea()
            while orden is not None:        # una orden puede interrumpir un movimiento con otra
                orden = atender(orden, consola)
            time.sleep_ms(20)
    finally:
        soltar()
        print("# programa detenido: motor suelto")


if __name__ == "__main__":
    arrancar()
