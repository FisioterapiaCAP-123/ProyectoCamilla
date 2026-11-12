"""Programa del ESP32 de la camilla (MicroPython).

Se guarda en la placa como main.py con Thonny y arranca solo al recibir energia.
Recibe las ordenes de la Raspberry por el cable USB y mueve las piernas con un
puente H BTS7960 (o L298N) o, con MODULO = "reles", la cabeza con el modulo de 4 reles.

Ordenes que recibe, una por linea, terminadas en *XX (comprobacion en hexadecimal):
    M piernas 1    mover la seccion: 1 extiende, -1 retrae. Se debe repetir cada 200 ms
    S piernas      detener esa seccion
    X              detener todo
    P              la Raspberry sigue conectada

A cada orden valida responde:
    E piernas=detenido*XX

Seguridad:
    - Una seccion se detiene sola si pasan LIMITE_SIN_ORDEN_MS sin recibir su M.
    - Con la primera orden de la Raspberry se activa el watchdog: si el programa
      se cuelga, la placa se reinicia y los reles quedan apagados.
"""
import select
import sys
import time

import machine
from machine import PWM, Pin

# ---------- CONFIGURACION ----------
MODULO = "puente"           # "puente": piernas con BTS7960 o L298N | "reles": cabeza con 4 reles
PIN_EXTENDER = 26           # puente H: RPWM del BTS7960 o IN1 del L298N
PIN_RETRAER = 27            # puente H: LPWM del BTS7960 o IN2 del L298N
PIN_HABILITAR = None        # puente H: ENA o R_EN+L_EN; None si van con jumper o a 3.3 V
VELOCIDAD = 100             # puente H: potencia en % (0 a 100)
FRECUENCIA_PWM = 1000       # puente H: Hz
ACTIVO_BAJO = True          # reles: True si el modulo se activa con 0
PAUSA_CAMBIO_MS = 300       # pausa entre apagar un motor y volver a arrancarlo
LIMITE_SIN_ORDEN_MS = 500   # sin ordenes durante este tiempo, la seccion se detiene
WATCHDOG_MS = 2000          # si el programa se cuelga este tiempo, la placa se reinicia
LARGO_MAXIMO = 64           # una linea mas larga se descarta
# -----------------------------------

APAGADO = 1 if ACTIVO_BAJO else 0
NOMBRE_ESTADO = {None: "detenido", "a": "extendiendo", "b": "contrayendo"}
DIRECCIONES = {"1": "a", "-1": "b"}

led = Pin(2, Pin.OUT, value=0)
perro = None


def poner_rele(rele, encendido):
    if ACTIVO_BAJO:
        rele.value(0 if encendido else 1)
    else:
        rele.value(1 if encendido else 0)


class ParReles:
    """Dos reles que mueven un actuador: nunca se encienden al mismo tiempo."""

    def __init__(self, pin_a, pin_b):
        self.a = Pin(pin_a, Pin.OUT, value=APAGADO)
        self.b = Pin(pin_b, Pin.OUT, value=APAGADO)

    def detener(self):
        poner_rele(self.a, False)
        poner_rele(self.b, False)

    def encender(self, cual):
        self.detener()
        poner_rele(self.a if cual == "a" else self.b, True)


def salida_pwm(numero):
    """Salida PWM que empieza apagada (algunas versiones arrancan el PWM a medias)."""
    pin = Pin(numero, Pin.OUT, value=0)
    try:
        pwm = PWM(pin, freq=FRECUENCIA_PWM, duty_u16=0)
    except TypeError:
        pwm = PWM(pin, freq=FRECUENCIA_PWM)
    pwm.duty_u16(0)
    return pwm


class PuenteH:
    """Un canal de L298N o un BTS7960: "a" extiende y "b" retrae, nunca los dos a la vez."""

    def __init__(self, pin_a, pin_b, pin_habilitar=None):
        self.a = salida_pwm(pin_a)
        self.b = salida_pwm(pin_b)
        self.habilitar = None if pin_habilitar is None else Pin(pin_habilitar, Pin.OUT, value=0)

    def detener(self):
        self.a.duty_u16(0)
        self.b.duty_u16(0)
        if self.habilitar is not None:
            self.habilitar.value(0)

    def encender(self, cual):
        self.detener()
        if self.habilitar is not None:
            self.habilitar.value(1)
        potencia = max(0, min(100, VELOCIDAD)) * 65535 // 100
        (self.a if cual == "a" else self.b).duty_u16(potencia)


class Seccion:
    """Actuadores que se mueven juntos, en la misma direccion (pares de reles o puentes H)."""

    def __init__(self, pares):
        self.pares = pares
        self.marcha = None      # direccion en la que estan encendidos los reles
        self.pedido = None      # direccion que pide la Raspberry
        self.visto = 0          # cuando llego la ultima orden de mover
        self.libre_desde = None  # antes de este momento no se puede arrancar

    def apagar_reles(self):
        for par in self.pares:
            par.detener()
        if self.marcha is not None:
            self.marcha = None
            self.libre_desde = time.ticks_add(time.ticks_ms(), PAUSA_CAMBIO_MS)

    def detener(self):
        self.pedido = None
        self.apagar_reles()

    def mover(self, cual, ahora):
        self.visto = ahora
        self.pedido = cual
        if self.marcha is not None and self.marcha != cual:
            self.apagar_reles()     # no se invierte el motor sin hacer la pausa

    def atender(self, ahora):
        if self.libre_desde is not None and time.ticks_diff(ahora, self.libre_desde) >= 0:
            self.libre_desde = None
        if self.pedido is None:
            return
        if time.ticks_diff(ahora, self.visto) > LIMITE_SIN_ORDEN_MS:
            self.detener()
            return
        if self.marcha is None and self.libre_desde is None:
            for par in self.pares:      # arrancan juntos
                par.encender(self.pedido)
            self.marcha = self.pedido


# Una entrada por seccion. Los nombres deben ser los de la pagina: altura, cabeza, piernas.
# Con puente H, los dos actuadores de piernas van en paralelo en el mismo BTS7960.
if MODULO == "reles":
    SECCIONES = {
        "cabeza": Seccion([ParReles(26, 27), ParReles(25, 33)]),
    }
else:
    SECCIONES = {
        "piernas": Seccion([PuenteH(PIN_EXTENDER, PIN_RETRAER, PIN_HABILITAR)]),
    }


def detener_todo():
    for seccion in SECCIONES.values():
        seccion.detener()
    led.value(0)


def comprobacion(texto):
    suma = 0
    for letra in texto:
        suma ^= ord(letra)
    return "%02X" % suma


def responder():
    partes = ["%s=%s" % (nombre, NOMBRE_ESTADO[SECCIONES[nombre].marcha]) for nombre in sorted(SECCIONES)]
    texto = "E " + " ".join(partes)
    print(texto + "*" + comprobacion(texto))


def procesar(linea, ahora):
    global perro
    separador = linea.rfind("*")
    if separador < 0:
        return
    texto = linea[:separador]
    if linea[separador + 1:].strip() != comprobacion(texto):
        return      # linea danada: se ignora y, si era un mover, la seccion se detiene sola

    if perro is None:
        perro = machine.WDT(timeout=WATCHDOG_MS)

    partes = texto.split(" ")
    orden = partes[0]
    if orden == "M" and len(partes) == 3 and partes[1] in SECCIONES and partes[2] in DIRECCIONES:
        SECCIONES[partes[1]].mover(DIRECCIONES[partes[2]], ahora)
    elif orden == "S" and len(partes) == 2 and partes[1] in SECCIONES:
        SECCIONES[partes[1]].detener()
    elif orden == "X" and len(partes) == 1:
        detener_todo()
    responder()


def bucle():
    entrada = select.poll()
    entrada.register(sys.stdin, select.POLLIN)
    lector = getattr(sys.stdin, "buffer", sys.stdin)
    linea = ""
    while True:
        ahora = time.ticks_ms()
        if perro is not None:
            perro.feed()

        for _ in range(LARGO_MAXIMO):
            if not entrada.poll(0):
                break
            dato = lector.read(1)
            if not dato:
                break
            codigo = dato[0] if isinstance(dato, bytes) else ord(dato)
            if codigo == 10:        # fin de linea
                procesar(linea, ahora)
                linea = ""
            elif codigo != 13:
                linea = linea + chr(codigo) if len(linea) < LARGO_MAXIMO else ""

        activo = False
        for seccion in SECCIONES.values():
            seccion.atender(ahora)
            activo = activo or seccion.marcha is not None
        led.value(1 if activo else 0)
        time.sleep_ms(5)


def arrancar():
    detener_todo()
    print("# camilla lista")
    try:
        bucle()
    except KeyboardInterrupt:
        detener_todo()
        if perro is not None:   # el watchdog no se puede apagar: se reinicia para dejar entrar a Thonny
            machine.reset()
    except Exception as error:
        detener_todo()
        print("# error:", error)
        time.sleep_ms(200)
        machine.reset()


if __name__ == "__main__":
    arrancar()
