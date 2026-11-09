"""Puente entre el servidor y los motores.

Simulador: sin placa, no mueve nada (para desarrollar con --simulador).
Esp32Serial: habla con esp32/main.py por USB.

Ningun metodo espera al puerto: mover() y parar() solo dejan la orden lista y un
hilo propio la envia, porque se llaman con `candado` tomado.
"""
import os
import threading
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None

SECCIONES = ("altura", "cabeza", "piernas")
BAUDIOS = 115200
CADA_ORDEN = 0.2  # segundos entre repeticiones: el ESP32 para si pasan 0.5 s sin recibir una
SILENCIO_MAXIMO = 1.0  # segundos sin respuesta para dar al ESP32 por desconectado
SILENCIO_REABRIR = 3.0  # segundos sin respuesta para cerrar y reabrir el puerto: Linux puede dejarlo mudo sin dar error
ESPERA_ARRANQUE = 6.0  # al abrir el puerto la placa se reinicia: tiempo para su primera respuesta
ESPERA_REINTENTO = 2.0  # segundos entre intentos de abrir el puerto
CHIPS_USB = {0x10C4, 0x1A86, 0x0403}  # conversores de las placas ESP32: CP210x, CH340 y FTDI


class Simulador:
    simulado = True

    def iniciar(self):
        pass

    def disponible(self, seccion):
        return True

    def mover(self, seccion, direccion):
        pass

    def parar(self):
        pass

    def estado(self):
        return {"conectado": True, "secciones": list(SECCIONES)}


def comprobacion(texto):
    suma = 0
    for letra in texto.encode():
        suma ^= letra
    return f"{suma:02X}"


def con_comprobacion(texto):
    return f"{texto}*{comprobacion(texto)}\n".encode()


def leer_respuesta(linea):
    """Las secciones que informa una linea "E cabeza=detenido*XX", o None si no es valida."""
    texto, separador, suma = linea.strip().rpartition("*")
    if not separador or not texto.startswith("E ") or suma != comprobacion(texto):
        return None
    return [parte.split("=")[0] for parte in texto.split(" ")[1:] if parte.split("=")[0] in SECCIONES]


class Esp32Serial:
    simulado = False

    def __init__(self, anotar):
        self.anotar = anotar
        self.bloqueo = threading.Lock()
        self.despertar = threading.Event()
        self.orden = None  # (seccion, direccion) mientras un motor deba seguir en marcha
        self.pendiente_parar = False
        self.secciones = []
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

    def estado(self):
        return {"conectado": self.vivo(), "secciones": list(self.secciones) if self.vivo() else []}

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

    def avisar(self, texto):
        if texto != self.avisado:
            self.avisado = texto
            self.anotar(texto)

    def siguiente_linea(self):
        with self.bloqueo:
            if self.pendiente_parar:
                self.pendiente_parar = False
                return con_comprobacion("X")
            if self.orden:
                return con_comprobacion(f"M {self.orden[0]} {self.orden[1]}")
        return con_comprobacion("P")

    def atender(self, puerto):
        recibido = b""
        proxima = 0.0
        limite = time.monotonic() + ESPERA_ARRANQUE  # sin respuesta valida hasta aqui, se reabre el puerto
        while True:
            cambio = self.despertar.wait(0.02)
            self.despertar.clear()
            ahora = time.monotonic()
            if cambio or ahora >= proxima:
                puerto.write(self.siguiente_linea())
                proxima = ahora + CADA_ORDEN
            if puerto.in_waiting:
                recibido += puerto.read(puerto.in_waiting)
            *lineas, recibido = recibido.split(b"\n")
            recibido = recibido[-256:]  # ruido sin fin de linea: no se acumula
            for linea in lineas:
                secciones = leer_respuesta(linea.decode("ascii", "ignore"))
                if secciones is not None:
                    self.secciones = secciones
                    self.visto = time.monotonic()
                    limite = self.visto + SILENCIO_REABRIR
                    self.avisar(f"ESP32 conectado en {puerto.port}: {', '.join(secciones)}")
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
                self.avisar(f"se perdio la conexion con el ESP32: {error}")
            finally:
                try:
                    puerto.close()
                except OSError:
                    pass
            time.sleep(ESPERA_REINTENTO)
