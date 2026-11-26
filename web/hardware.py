"""Puente entre el servidor y los motores.

Simulador: sin placa, no mueve nada (para desarrollar con --simulador). Simula los
    sensores de angulo de cabeza y piernas, que cambian mientras la seccion se mueve.
Esp32Serial: habla con esp32/main.py por USB.

estado()["sensores"]: {"piernas": {"angulo": 12.5 o None, "estado": "ok"|"falla"|"sincal"|"plano"|"poco"}},
solo de las secciones con sensor de angulo (MPU6050).

Ningun metodo espera al puerto: mover() y parar() solo dejan la orden lista y un
hilo propio la envia, porque se llaman con `candado` tomado.
"""
import math
import os
import threading
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None

SECCIONES = ("altura", "cabeza", "piernas")
ESTADOS_SENSOR = ("falla", "sincal", "plano", "poco")  # sin angulo: no responde, sin calibrar, falta "subido", subido muy cerca
BAUDIOS = 115200
CADA_ORDEN = 0.2  # segundos entre repeticiones: el ESP32 para si pasan 0.5 s sin recibir una
SILENCIO_MAXIMO = 1.0  # segundos sin respuesta para dar al ESP32 por desconectado
SILENCIO_REABRIR = 3.0  # segundos sin respuesta para cerrar y reabrir el puerto: Linux puede dejarlo mudo sin dar error
ESPERA_ARRANQUE = 6.0  # al abrir el puerto la placa se reinicia: tiempo para su primera respuesta
ESPERA_REINTENTO = 2.0  # segundos entre intentos de abrir el puerto
CHIPS_USB = {0x10C4, 0x1A86, 0x0403}  # conversores de las placas ESP32: CP210x, CH340 y FTDI


class Simulador:
    simulado = True
    GRADOS_POR_SEGUNDO = {"cabeza": 3.0, "piernas": 4.0}
    RANGO = {"cabeza": (-30.0, 70.0), "piernas": (0.0, 45.0)}
    CALIBRACION_MINIMA = 15  # grados, igual que en esp32/main.py

    def __init__(self):
        self.real = {s: 0.0 for s in self.RANGO}  # angulo "fisico" de cada seccion
        self.cero = {s: 0.0 for s in self.RANGO}  # donde se guardo "plano"
        self.calibrado = {s: "ok" for s in self.RANGO}
        self.marcha = None  # (seccion, direccion, desde)

    def iniciar(self):
        pass

    def disponible(self, seccion):
        return True

    def avanzar(self):
        if not self.marcha:
            return
        seccion, direccion, desde = self.marcha
        ahora = time.monotonic()
        if seccion in self.real:
            minimo, maximo = self.RANGO[seccion]
            cambio = direccion * self.GRADOS_POR_SEGUNDO[seccion] * (ahora - desde)
            self.real[seccion] = max(minimo, min(maximo, self.real[seccion] + cambio))
        self.marcha = (seccion, direccion, ahora)

    def mover(self, seccion, direccion):
        self.avanzar()
        if not self.marcha or self.marcha[:2] != (seccion, direccion):
            self.marcha = (seccion, direccion, time.monotonic())

    def parar(self):
        self.avanzar()
        self.marcha = None

    def calibrar(self, seccion, posicion):
        self.avanzar()
        if posicion == "plano":
            self.cero[seccion] = self.real[seccion]
            self.calibrado[seccion] = "plano"
        elif self.calibrado[seccion] != "sincal":
            lejos = abs(self.real[seccion] - self.cero[seccion]) >= self.CALIBRACION_MINIMA
            self.calibrado[seccion] = "ok" if lejos else "poco"

    def depuracion(self):
        return {"puerto": "simulador", "ultima_orden": str(self.marcha[:2]) if self.marcha else "",
                "ultima_respuesta": "", "hace_ms": 0}

    def estado(self):
        self.avanzar()
        sensores = {s: {"angulo": round(self.real[s] - self.cero[s], 1) if self.calibrado[s] == "ok" else None,
                        "estado": self.calibrado[s]} for s in self.RANGO}
        return {"conectado": True, "secciones": list(SECCIONES), "sensores": sensores}


def comprobacion(texto):
    suma = 0
    for letra in texto.encode():
        suma ^= letra
    return f"{suma:02X}"


def con_comprobacion(texto):
    return f"{texto}*{comprobacion(texto)}\n".encode()


def leer_angulo(valor):
    """"12.5" -> angulo; "sincal", "plano"... -> por que no hay angulo."""
    if valor in ESTADOS_SENSOR:
        return {"angulo": None, "estado": valor}
    try:
        angulo = float(valor)
    except ValueError:
        return {"angulo": None, "estado": "falla"}
    if not math.isfinite(angulo):
        return {"angulo": None, "estado": "falla"}
    return {"angulo": round(angulo, 1), "estado": "ok"}


def leer_respuesta(linea):
    """Lo que informa una linea "E cabeza=detenido ang_piernas=12.5*XX", o None si no es valida:
    {"secciones": ["cabeza", ...], "sensores": {"piernas": {"angulo": 12.5, "estado": "ok"}}}."""
    texto, separador, suma = linea.strip().rpartition("*")
    if not separador or not texto.startswith("E ") or suma != comprobacion(texto):
        return None
    secciones, sensores = [], {}
    for parte in texto.split(" ")[1:]:
        clave, _, valor = parte.partition("=")
        if clave in SECCIONES:
            secciones.append(clave)
        elif clave.startswith("ang_") and clave[4:] in SECCIONES:
            sensores[clave[4:]] = leer_angulo(valor)
    return {"secciones": secciones, "sensores": sensores}


class Esp32Serial:
    simulado = False

    def __init__(self, anotar):
        self.anotar = anotar
        self.bloqueo = threading.Lock()
        self.despertar = threading.Event()
        self.orden = None  # (seccion, direccion) mientras un motor deba seguir en marcha
        self.pendiente_parar = False
        self.calibraciones = []  # [(seccion, "plano"|"subido")] por mandar, una por vez
        self.secciones = []
        self.sensores = {}  # lo ultimo que dijo el ESP32 de cada sensor de angulo
        self.avisado_sensor = {}  # ultimo estado de cada sensor anotado en el registro
        self.puerto = None  # para la depuracion: puerto abierto, ultima linea enviada y ultima respuesta
        self.ultima_orden = ""
        self.ultima_respuesta = ""
        self.visto = None  # cuando llego la ultima respuesta valida
        self.avisado = None  # ultimo estado anotado en el registro

    def iniciar(self):
        if serial is None:
            self.anotar("falta pyserial: sudo apt install python3-serial")
            return
        threading.Thread(target=self.trabajar, daemon=True).start()

    # ---------- lo que usa el servidor ----------
    def vivo(self):
        return self.visto is not None and time.monotonic() - self.visto < SILENCIO_MAXIMO

    def disponible(self, seccion):
        return self.vivo() and seccion in self.secciones

    def mover(self, seccion, direccion):
        with self.bloqueo:
            cambio = self.orden != (seccion, direccion)
            self.orden = (seccion, direccion)
        if cambio:
            self.despertar.set()

    def parar(self):
        with self.bloqueo:
            self.orden = None
            self.pendiente_parar = True
        self.despertar.set()

    def depuracion(self):
        visto = self.visto
        return {"puerto": self.puerto, "ultima_orden": self.ultima_orden, "ultima_respuesta": self.ultima_respuesta,
                "hace_ms": None if visto is None else int((time.monotonic() - visto) * 1000)}

    def calibrar(self, seccion, posicion):
        with self.bloqueo:
            self.calibraciones.append((seccion, posicion))
        self.despertar.set()

    def estado(self):
        vivo = self.vivo()
        return {"conectado": vivo, "secciones": list(self.secciones) if vivo else [],
                "sensores": dict(self.sensores) if vivo else {}}

    # ---------- hilo del puerto ----------
    def buscar_puerto(self):
        elegido = os.environ.get("CAMILLA_PUERTO")
        if elegido:
            return elegido
        return next((p.device for p in list_ports.comports() if p.vid in CHIPS_USB), None)

    def abrir(self):
        while True:
            ruta = self.buscar_puerto()
            if ruta:
                puerto = serial.Serial()
                puerto.port = ruta
                puerto.baudrate = BAUDIOS
                puerto.timeout = 0
                puerto.write_timeout = 0.5
                puerto.exclusive = True  # si Thonny lo tiene abierto, no se comparte
                puerto.dtr = False  # con estas dos lineas en alto la placa se queda reiniciando
                puerto.rts = False
                try:
                    puerto.open()
                    return puerto
                except OSError as error:
                    self.avisar(f"no se pudo abrir el puerto del ESP32 ({ruta}): {error}")
            else:
                self.avisar("no se encontro el ESP32 en ningun puerto USB")
            time.sleep(ESPERA_REINTENTO)

    def anotar_sensores(self):
        """Deja en el registro cuando un sensor de angulo cambia de estado (no cada lectura)."""
        for seccion, sensor in self.sensores.items():
            if self.avisado_sensor.get(seccion) != sensor["estado"]:
                self.avisado_sensor[seccion] = sensor["estado"]
                self.anotar(f"sensor de angulo de {seccion}: {sensor['estado']}")

    def avisar(self, texto):
        if texto != self.avisado:
            self.avisado = texto
            self.anotar(texto)

    def siguiente_linea(self):
        with self.bloqueo:
            if self.pendiente_parar:
                self.pendiente_parar = False
                return con_comprobacion("X")
            if self.calibraciones:
                seccion, posicion = self.calibraciones.pop(0)
                return con_comprobacion(f"C {seccion} {posicion}")
            if self.orden:
                return con_comprobacion(f"M {self.orden[0]} {self.orden[1]}")
        return con_comprobacion("P")

    def atender(self, puerto):
        self.puerto = puerto.port
        recibido = b""
        proxima = 0.0
        limite = time.monotonic() + ESPERA_ARRANQUE  # sin respuesta valida hasta aqui, se reabre el puerto
        while True:
            cambio = self.despertar.wait(0.02)
            self.despertar.clear()
            ahora = time.monotonic()
            if cambio or ahora >= proxima:
                linea = self.siguiente_linea()
                puerto.write(linea)
                self.ultima_orden = linea.decode("ascii", "replace").strip()
                proxima = ahora + CADA_ORDEN
            if puerto.in_waiting:
                recibido += puerto.read(puerto.in_waiting)
            *lineas, recibido = recibido.split(b"\n")
            recibido = recibido[-256:]  # ruido sin fin de linea: no se acumula
            for linea in lineas:
                respuesta = leer_respuesta(linea.decode("ascii", "ignore"))
                if respuesta is not None:
                    self.secciones = respuesta["secciones"]
                    self.sensores = respuesta["sensores"]
                    self.ultima_respuesta = linea.decode("ascii", "replace").strip()
                    self.visto = time.monotonic()
                    limite = self.visto + SILENCIO_REABRIR
                    self.avisar(f"ESP32 conectado en {puerto.port}: {', '.join(self.secciones)}")
                    self.anotar_sensores()
            if self.visto is not None and not self.vivo():
                self.avisar("el ESP32 dejo de responder")
            if ahora >= limite:
                raise OSError("dejo de responder" if self.visto is not None
                              else "no respondio al abrir el puerto (revisa que tenga cargado esp32/main.py)")

    def trabajar(self):
        while True:
            puerto = self.abrir()
            try:
                self.atender(puerto)
            except Exception as error:  # el cable se desconecto o el puerto fallo: se vuelve a intentar
                self.visto = None
                self.puerto = None
                self.avisar(f"se perdio la conexion con el ESP32: {error}")
            finally:
                try:
                    puerto.close()
                except OSError:
                    pass
            time.sleep(ESPERA_REINTENTO)
