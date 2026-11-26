"""Programa del ESP32 de la camilla (MicroPython).

Se guarda en la placa como main.py con Thonny y arranca solo al recibir energia.
Recibe las ordenes de la Raspberry por el cable USB y mueve las piernas con un
puente H BTS7960, la cabeza con un L298N y la altura con un motor paso a paso
(NEMA 17 con driver DRV8825). Con MODULO = "reles", solo la cabeza, con el
modulo de 4 reles.

Altura, ESP32 -> DRV8825 (placa morada; STEP se llama STP):
    GPIO 25 -> STP
    GPIO 33 -> DIR
    GPIO 26 -> EN        (activo en bajo: 0 = motor con fuerza, 1 = suelto)
    3.3 V   -> RST y SLP (los dos juntos)
    GND     -> GND del driver, comun con el GND de la fuente del motor
    Fuente del motor (12-24 V) -> VMOT y GND, con un capacitor de 100 uF o mas junto
        al driver. La fuente va SOLO al driver: nunca al motor ni al ESP32.
    M0, M1, M2 sin conectar = paso completo (PASOS_* estan en pasos completos)
DRV8825 -> NEMA 17: 1A, 2A -> bobina A; 1B, 2B -> bobina B (en otras placas A1, A2,
    B1, B2). La pareja de una bobina suena en continuidad con el multimetro. Si gira
    al reves no se cambian cables: se cambia SUBIR_CON_DIR.
Corriente del driver = Vref x 2 (Vref entre el potenciometro y GND).
La altura no tiene finales de carrera: se mueve solo mientras se mantiene el boton.
Nunca conectar o desconectar el motor con la fuente encendida: se quema el driver.

Pines de la placa propia (25-11): EN de la altura en el 26 y extender piernas en
el 13 (antes 13 y 26). Con la protoboard vieja hay que cambiar esos dos cables.

Finales de carrera de piernas: contacto NC del microswitch entre el GPIO y GND
(C y NC; sin resistencia, se usa la interna). GPIO 17 = arriba (al extender),
GPIO 16 = abajo (al retraer). Con un final tocado no se mueve hacia ese lado, si
se puede hacia el otro. Un cable cortado se lee como tocado: tambien para.

Angulo real de piernas y cabeza: un MPU6050 (modulo GY-521) debajo de cada seccion,
los dos en el mismo I2C (SDA 21, SCL 22). Piernas con AD0 a GND (0x68), cabeza con
AD0 a VCC (0x69). Se calibra desde la pagina con la seccion quieta: primero "plano"
(a 0 grados) y despues "subido" (unos 30 grados). Con esas dos lecturas el ESP32 sabe
alrededor de que eje gira la seccion, asi que no importa como quedo montado el modulo.
La calibracion queda en calibracion.json, en la memoria del ESP32.

Ordenes que recibe, una por linea, terminadas en *XX (comprobacion en hexadecimal):
    M piernas 1        mover la seccion: 1 extiende, -1 retrae. Se debe repetir cada 200 ms
    S piernas          detener esa seccion
    X                  detener todo
    P                  la Raspberry sigue conectada
    C piernas plano    calibrar el MPU de esa seccion (plano o subido), con la seccion quieta

A cada orden valida responde con el estado de todas las secciones:
    E cabeza=detenido piernas=detenido final_piernas=no ang_piernas=12.5*XX
    final_piernas: no, arriba, abajo o falla (los dos tocados: revisar cables)
    ang_piernas: el angulo en grados, o falla (el MPU no responde), sincal (sin
        calibrar), plano (falta "subido") o poco ("subido" quedo muy cerca de "plano")

Seguridad:
    - Una seccion se detiene sola si pasan LIMITE_SIN_ORDEN_MS sin recibir su M.
    - Piernas se detiene al tocar su final de carrera (PIERNAS_FINAL_ARRIBA/ABAJO).
    - Un MPU que falla no detiene nada: los motores siguen y la linea E dice "falla".
    - Con la primera orden de la Raspberry se activa el watchdog: si el programa
      se cuelga, la placa se reinicia y los reles quedan apagados.
"""
import json
import math
import select
import struct
import sys
import time

import machine
from machine import I2C, PWM, Pin

# ---------- CONFIGURACION ----------
MODULO = "puente"           # "puente": piernas (BTS7960) y cabeza (L298N) | "reles": cabeza con 4 reles
PIN_EXTENDER = 13           # piernas, BTS7960: RPWM (placa J5; antes 26)
PIN_RETRAER = 27            # piernas, BTS7960: LPWM
PIN_HABILITAR = None        # piernas, BTS7960: R_EN+L_EN; None si van a 3.3 V
PIERNAS_FINAL_ARRIBA = 17   # piernas: final de carrera al extender (subir); None si no esta conectado
PIERNAS_FINAL_ABAJO = 16    # piernas: final de carrera al retraer (bajar); None si no esta conectado
FINAL_ACTIVO = 1            # lo que lee el pin con el final TOCADO: 1 = contacto NC a GND (si se corta
                            #   el cable tambien para); 0 = contacto NO a GND
CABEZA_EXTENDER = 18        # cabeza, L298N: IN1 (ENA con su jumper)
CABEZA_RETRAER = 19         # cabeza, L298N: IN2
VELOCIDAD = 100             # puente H: potencia en % (0 a 100)
FRECUENCIA_PWM = 1000       # puente H: Hz
ALTURA_STEPPER = True       # altura con motor paso a paso; False si no esta conectado
ALTURA_STEP = 25            # altura, DRV8825: STP (cada pulso es un paso)
ALTURA_DIR = 33             # altura, DRV8825: DIR
ALTURA_EN = 26              # altura, DRV8825: EN (0 = con fuerza, 1 = suelto; antes 13)
SUBIR_CON_DIR = 1           # altura: si "Subir" baja, cambiar a 0
PASOS_VELOCIDAD = 1000      # altura: pasos por segundo a toda velocidad (5 vueltas/s en paso completo,
                            #         casi el maximo de un NEMA 17 a 12 V). Si zumba o salta pasos: 800 o 600
PASOS_INICIO = 250          # altura: a esta velocidad arranca; mas rapido de golpe no arranca con carga
PASOS_ACELERACION = 1500    # altura: cuanto sube la velocidad cada segundo (llega al maximo en 0.5 s)
MANTENER_FUERZA = True      # altura: detenido, el motor sigue sujetando (se calienta)
PIERNAS_MPU = 0x68          # piernas: direccion de su MPU6050 (AD0 a GND); None si no esta conectado
CABEZA_MPU = None           # cabeza: 0x69 (AD0 a VCC) cuando se conecte; None si no esta conectado
MPU_SDA = 21                # MPU6050: los dos modulos comparten SDA y SCL
MPU_SCL = 22
MPU_FRECUENCIA = 50000      # MPU6050: Hz del I2C; si falla con cables largos, 20000
MPU_CADA_MS = 100           # MPU6050: cada cuanto se lee cada modulo
MPU_SUAVIZADO = 0.3         # MPU6050: cuanto pesa cada lectura nueva (0 a 1; menos = mas suave y mas lento)
CALIBRACION_MINIMA = 15     # MPU6050: grados que "subido" tiene que quedar lejos de "plano"
ARCHIVO_CALIBRACION = "calibracion.json"   # en la memoria del ESP32: cargar main.py no lo borra
ACTIVO_BAJO = True          # reles: True si el modulo se activa con 0
PAUSA_CAMBIO_MS = 300       # pausa entre apagar un motor y volver a arrancarlo
LIMITE_SIN_ORDEN_MS = 500   # sin ordenes durante este tiempo, la seccion se detiene
WATCHDOG_MS = 2000          # si el programa se cuelga este tiempo, la placa se reinicia
LARGO_MAXIMO = 64           # una linea mas larga se descarta
# -----------------------------------

APAGADO = 1 if ACTIVO_BAJO else 0
NOMBRE_ESTADO = {None: "detenido", "a": "extendiendo", "b": "contrayendo"}
DIRECCIONES = {"1": "a", "-1": "b"}
NOMBRE_FINAL = {"": "no", "a": "arriba", "b": "abajo", "ab": "falla"}   # "ab": los dos a la vez = cable suelto

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


def salida_pwm(numero, frecuencia=FRECUENCIA_PWM):
    """Salida PWM que empieza apagada (algunas versiones arrancan el PWM a medias)."""
    pin = Pin(numero, Pin.OUT, value=0)
    try:
        pwm = PWM(pin, freq=frecuencia, duty_u16=0)
    except TypeError:
        pwm = PWM(pin, freq=frecuencia)
    pwm.duty_u16(0)
    return pwm


class Stepper:
    """Motor paso a paso con DRV8825. El PWM en STEP da los pulsos solo (uno por paso):
    su frecuencia es la velocidad. "a" sube y "b" baja. Arranca despacio y acelera."""

    def __init__(self, pin_step, pin_dir, pin_en):
        self.step = salida_pwm(pin_step, PASOS_INICIO)
        self.dir = Pin(pin_dir, Pin.OUT, value=0)
        self.en = Pin(pin_en, Pin.OUT, value=0 if MANTENER_FUERZA else 1)
        self.velocidad = 0
        self.desde = 0

    def poner_velocidad(self, pasos):
        if pasos == FRECUENCIA_PWM:
            pasos += 1      # con la misma frecuencia compartiria reloj con los puentes H
        self.velocidad = pasos
        self.step.freq(pasos)
        self.step.duty_u16(32768)

    def detener(self):
        self.step.duty_u16(0)
        self.velocidad = 0
        if not MANTENER_FUERZA:
            self.en.value(1)

    def encender(self, cual):
        self.detener()
        self.dir.value(SUBIR_CON_DIR if cual == "a" else 1 - SUBIR_CON_DIR)
        self.en.value(0)
        time.sleep_ms(1)    # el driver necesita un momento tras cambiar DIR o EN
        self.desde = time.ticks_ms()
        self.poner_velocidad(min(PASOS_INICIO, PASOS_VELOCIDAD))

    def actualizar(self, ahora):
        """Rampa: sube la velocidad poco a poco hasta PASOS_VELOCIDAD."""
        if self.velocidad == 0 or self.velocidad >= PASOS_VELOCIDAD:
            return
        segundos = time.ticks_diff(ahora, self.desde) / 1000
        pasos = min(PASOS_VELOCIDAD, int(PASOS_INICIO + PASOS_ACELERACION * segundos))
        if pasos - self.velocidad >= 10 or pasos == PASOS_VELOCIDAD:
            self.poner_velocidad(pasos)


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


def entrada_final(numero):
    """Final de carrera entre el GPIO y GND, con la resistencia interna. None si no hay."""
    return None if numero is None else Pin(numero, Pin.IN, Pin.PULL_UP)


def cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def punto(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def grados_entre(a, b):
    """Angulo entre dos direcciones, de 0 a 180 grados."""
    c = cruz(a, b)
    return math.atan2(math.sqrt(punto(c, c)), punto(a, b)) * 57.29578


class Inclinometro:
    """MPU6050 (GY-521): mide hacia donde esta la gravedad. Con dos lecturas guardadas,
    la seccion en plano y la seccion subida, sabe alrededor de que eje gira la seccion:
    no importa como quedo montado el modulo. El angulo es positivo hacia "subido"."""

    def __init__(self, bus, direccion, guardado):
        self.bus = bus
        self.direccion = direccion
        self.gravedad = None    # lectura suavizada [x, y, z]; None si el modulo no responde
        self.fallos = 0         # lecturas fallidas seguidas
        self.reintento = 0      # sin respuesta, se vuelve a probar desde este momento
        self.plano = guardado.get("plano")
        self.subido = guardado.get("subido")
        self.poco = False       # el ultimo "subido" quedo demasiado cerca de "plano"
        self.eje = None         # eje de la bisagra (unitario), calculado con plano y subido
        self.preparar()
        self.despertar()

    def despertar(self):
        try:
            self.bus.writeto_mem(self.direccion, 0x6B, b"\x00")    # arranca dormido
            self.bus.writeto_mem(self.direccion, 0x1A, b"\x06")    # filtro de 5 Hz contra la vibracion
            return True
        except OSError:
            return False

    def preparar(self):
        self.eje = None
        if self.plano and self.subido:
            eje = cruz(self.plano, self.subido)
            largo = math.sqrt(punto(eje, eje))
            if largo > 0:
                self.eje = [c / largo for c in eje]

    def leer(self, ahora):
        if self.fallos >= 3 and time.ticks_diff(ahora, self.reintento) < 0:
            return      # no responde: se espera antes de volver a probar
        try:
            if self.fallos >= 3 and not self.despertar():
                raise OSError("sin respuesta")
            x, y, z = struct.unpack(">hhh", self.bus.readfrom_mem(self.direccion, 0x3B, 6))
        except OSError:
            self.fallos += 1
            if self.fallos >= 3:
                self.gravedad = None
                self.reintento = time.ticks_add(ahora, 1000)
            return
        self.fallos = 0
        if x == 0 and y == 0 and z == 0:    # se reinicio (cable flojo) y quedo dormido
            self.despertar()
            return
        if self.gravedad is None:
            self.gravedad = [x, y, z]
        else:
            self.gravedad = [g + (n - g) * MPU_SUAVIZADO for g, n in zip(self.gravedad, (x, y, z))]

    def angulo(self):
        if self.gravedad is None or self.eje is None:
            return None
        g = self.gravedad
        return math.atan2(punto(self.eje, cruz(self.plano, g)), punto(self.plano, g)) * 57.29578

    def estado(self):
        """Para la linea E: el angulo con un decimal, o por que no lo hay."""
        if self.gravedad is None:
            return "falla"
        if not self.plano:
            return "sincal"
        if self.eje is None:
            return "poco" if self.poco else "plano"
        return "%.1f" % self.angulo()

    def guardar(self, posicion):
        """La lectura actual pasa a ser "plano" o "subido". True si cambio la calibracion."""
        if self.gravedad is None:
            return False
        actual = [round(c) for c in self.gravedad]
        if posicion == "plano":
            self.plano, self.subido, self.poco = actual, None, False
        elif not self.plano:
            return False
        elif grados_entre(self.plano, actual) < CALIBRACION_MINIMA:
            self.poco = True
            return False
        else:
            self.subido, self.poco = actual, False
        self.preparar()
        return True


def leer_calibracion():
    try:
        with open(ARCHIVO_CALIBRACION) as archivo:
            return json.load(archivo)
    except (OSError, ValueError):
        return {}


class Seccion:
    """Actuadores que se mueven juntos, en la misma direccion (pares de reles o puentes H).
    finales: {"a": pin, "b": pin}, el final de carrera de cada direccion ("a" extiende o sube).
    Con su final tocado, la seccion no arranca hacia ese lado y, si iba, se detiene."""

    def __init__(self, pares, finales=None):
        self.pares = pares
        self.finales = {cual: pin for cual, pin in (finales or {}).items() if pin is not None}
        self.marcha = None      # direccion en la que estan encendidos los reles
        self.pedido = None      # direccion que pide la Raspberry
        self.visto = 0          # cuando llego la ultima orden de mover
        self.libre_desde = None  # antes de este momento no se puede arrancar

    def en_final(self, cual):
        pin = self.finales.get(cual)
        return pin is not None and pin.value() == FINAL_ACTIVO

    def topes(self):
        """Los finales tocados, para la linea E: "a", "b", "ab" o ""."""
        return "".join(cual for cual in "ab" if self.en_final(cual))

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
        if self.en_final(self.pedido):
            # Llego al final (o ya estaba): se apaga y no arranca hacia ese lado. El pedido
            # sigue: si fue ruido y el final se suelta, arranca otra vez tras la pausa
            if self.marcha is not None:
                self.apagar_reles()
            return
        if self.marcha is None and self.libre_desde is None:
            for par in self.pares:      # arrancan juntos
                par.encender(self.pedido)
            self.marcha = self.pedido
        elif self.marcha is not None:
            for par in self.pares:      # el stepper acelera mientras sigue en marcha
                if hasattr(par, "actualizar"):
                    par.actualizar(ahora)


# Una entrada por seccion. Los nombres deben ser los de la pagina: altura, cabeza, piernas.
# Con puente H, los dos actuadores de piernas van en paralelo en el mismo BTS7960.
# La cabeza tiene por ahora un solo actuador, en el canal A del L298N.
if MODULO == "reles":
    SECCIONES = {
        "cabeza": Seccion([ParReles(26, 27), ParReles(25, 33)]),
    }
else:
    SECCIONES = {
        "piernas": Seccion([PuenteH(PIN_EXTENDER, PIN_RETRAER, PIN_HABILITAR)],
                           {"a": entrada_final(PIERNAS_FINAL_ARRIBA), "b": entrada_final(PIERNAS_FINAL_ABAJO)}),
        "cabeza": Seccion([PuenteH(CABEZA_EXTENDER, CABEZA_RETRAER)]),
    }
    if ALTURA_STEPPER:
        try:
            SECCIONES["altura"] = Seccion([Stepper(ALTURA_STEP, ALTURA_DIR, ALTURA_EN)])
        except Exception as error:      # sin altura, cabeza y piernas siguen funcionando
            print("# altura desactivada:", error)

# Un MPU6050 por seccion, todos en el mismo I2C. Si falla, los motores siguen igual.
SENSORES = {}
_mpu = {nombre: direccion for nombre, direccion in (("piernas", PIERNAS_MPU), ("cabeza", CABEZA_MPU))
        if direccion is not None and nombre in SECCIONES}
if _mpu:
    try:
        _bus = I2C(0, scl=Pin(MPU_SCL), sda=Pin(MPU_SDA), freq=MPU_FRECUENCIA)
        _guardada = leer_calibracion()
        for _nombre, _direccion in _mpu.items():
            SENSORES[_nombre] = Inclinometro(_bus, _direccion, _guardada.get(_nombre, {}))
    except Exception as error:
        print("# sensores desactivados:", error)


def guardar_calibracion():
    datos = leer_calibracion()      # conserva la de un MPU que hoy no este conectado
    for nombre, sensor in SENSORES.items():
        datos[nombre] = {"plano": sensor.plano, "subido": sensor.subido}
    try:
        with open(ARCHIVO_CALIBRACION, "w") as archivo:
            json.dump(datos, archivo)
    except OSError as error:
        print("# no se pudo guardar la calibracion:", error)


def calibrar(nombre, posicion):
    if SECCIONES[nombre].marcha is not None:
        return      # en marcha la lectura se mueve: solo con la seccion quieta
    if SENSORES[nombre].guardar(posicion):
        guardar_calibracion()


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
    partes += ["final_%s=%s" % (nombre, NOMBRE_FINAL[SECCIONES[nombre].topes()])
               for nombre in sorted(SECCIONES) if SECCIONES[nombre].finales]
    partes += ["ang_%s=%s" % (nombre, SENSORES[nombre].estado()) for nombre in sorted(SENSORES)]
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
    elif orden == "C" and len(partes) == 3 and partes[1] in SENSORES and partes[2] in ("plano", "subido"):
        calibrar(partes[1], partes[2])
    responder()


def bucle():
    entrada = select.poll()
    entrada.register(sys.stdin, select.POLLIN)
    lector = getattr(sys.stdin, "buffer", sys.stdin)
    linea = ""
    proxima_lectura = time.ticks_ms()
    while True:
        ahora = time.ticks_ms()
        if perro is not None:
            perro.feed()

        if SENSORES and time.ticks_diff(ahora, proxima_lectura) >= 0:
            proxima_lectura = time.ticks_add(ahora, MPU_CADA_MS)
            for sensor in SENSORES.values():
                sensor.leer(ahora)

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
    for nombre in sorted(SECCIONES):
        if SECCIONES[nombre].finales:
            print("# finales de %s: %s" % (nombre, NOMBRE_FINAL[SECCIONES[nombre].topes()]))
    for nombre in sorted(SENSORES):
        SENSORES[nombre].leer(time.ticks_ms())
        print("# sensor de %s: %s" % (nombre, SENSORES[nombre].estado()))
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
