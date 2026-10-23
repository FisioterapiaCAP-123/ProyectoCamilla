#!/usr/bin/env python3
"""Servidor web sencillo: 3 botones que envian comandos al ESP32 por USB serial
y muestran la respuesta que devuelve el ESP32. Solo un dispositivo (el que tiene
el control) puede mandar ordenes a la vez. Antes se inicia sesion con un nombre
(sin contraseña) para saber quien tiene el control.

Uso:  python3 servidor.py            (busca /dev/ttyUSB0 o /dev/ttyACM0)
      PUERTO=/dev/ttyUSB1 python3 servidor.py
Luego abrir en el navegador: http://localhost:8000  (o http://IP-de-la-raspberry:8000)
"""
import glob
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import serial

BAUDIOS = 115200
PUERTO_WEB = 8000
IP_RED = "10.42.0.1"  # IP de la Raspberry en su propia red WiFi "Camilla"
TIMEOUT_RESPUESTA = 2  # segundos esperando la respuesta del ESP32
COMANDOS_VALIDOS = {"1", "2", "3"}
COMANDO_DETENER = "0"  # se manda al ESP32 cada vez que cambia quien tiene el control
TIEMPO_LIBERAR = 60  # segundos sin noticias de la pagina que tiene el control para liberarlo

CARPETA = Path(__file__).parent  # los .html se leen en cada visita: al editarlos basta con recargar la pagina

esp = None
candado = threading.RLock()  # una cosa a la vez: el puerto serial y el control
dueno = None  # identificador de la pagina que tiene el control (None = libre)
nombre_dueno = ""  # nombre con el que inicio sesion quien tiene el control
visto = 0.0  # ultima vez que esa pagina se comunico


def buscar_puerto():
    if os.environ.get("PUERTO"):
        return os.environ["PUERTO"]
    puertos = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    return puertos[0] if puertos else None


def conectar():
    global esp
    puerto = buscar_puerto()
    if not puerto:
        raise RuntimeError("No se encontro el ESP32 (no hay /dev/ttyUSB* ni /dev/ttyACM*)")
    esp = serial.Serial(puerto, BAUDIOS, timeout=TIMEOUT_RESPUESTA)
    time.sleep(2)  # al abrir el puerto el ESP32 se reinicia; esperamos a que arranque
    esp.reset_input_buffer()
    print(f"Conectado al ESP32 en {puerto}")


def enviar(comando):
    with candado:
        if esp is None or not esp.is_open:
            conectar()
        esp.reset_input_buffer()
        esp.write((comando + "\n").encode())
        respuesta = esp.readline().decode(errors="replace").strip()
    return respuesta


def enviar_seguro(comando):
    """Como enviar(), pero devuelve (respuesta, error) en vez de lanzar excepciones."""
    global esp
    try:
        return enviar(comando), None
    except Exception as e:
        esp = None  # forzar reconexion en el siguiente intento
        return None, str(e)


def cambiar_dueno(nuevo, nombre=""):
    """Cambia quien tiene el control; si alguien lo pierde, detiene la camilla."""
    global dueno, nombre_dueno, visto
    anterior, dueno, nombre_dueno, visto = dueno, nuevo, nombre, time.monotonic()
    if anterior is not None and anterior != nuevo:
        enviar_seguro(COMANDO_DETENER)


def estado_control(dispositivo):
    """'tuyo', 'otro' o 'libre'. Libera el control si su pagina dejo de comunicarse."""
    global visto
    if dueno is not None and time.monotonic() - visto > TIEMPO_LIBERAR:
        cambiar_dueno(None)
    if dueno is None:
        return "libre"
    if dueno == dispositivo:
        visto = time.monotonic()
        return "tuyo"
    return "otro"


class Manejador(BaseHTTPRequestHandler):
    def do_GET(self):
        # Portal tipo "WiFi de hotel": en la red Camilla los celulares preguntan a
        # sitios como captive.apple.com si hay internet. Se les redirige a la pagina
        # y el celular la abre solo.
        host = (self.headers.get("Host") or "").split(":")[0]
        if self.connection.getsockname()[0] == IP_RED and host != IP_RED:
            self.send_response(302)
            self.send_header("Location", f"http://{IP_RED}:{PUERTO_WEB}/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        ruta = urlsplit(self.path).path
        dispositivo = self.headers.get("X-Dispositivo", "")  # lo manda la pagina
        nombre = unquote(self.headers.get("X-Nombre", "")).strip()[:30]  # el del inicio de sesion

        if ruta == "/":
            self.responder(200, (CARPETA / "login.html").read_bytes(), "text/html; charset=utf-8")
        elif ruta == "/control":
            self.responder(200, (CARPETA / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif ruta == "/estado":
            with candado:
                control = estado_control(dispositivo)
                quien = nombre_dueno
            self.json(200, {"control": control, "quien": quien})
        elif ruta == "/tomar":
            if not dispositivo:
                return self.json(400, {"error": "Falta el identificador del dispositivo"})
            with candado:
                estado_control(dispositivo)  # libera el control si estaba abandonado
                cambiar_dueno(dispositivo, nombre)
            self.log_message("%s tomo el control", nombre or "(sin nombre)")
            self.json(200, {"control": "tuyo", "quien": nombre})
        elif ruta == "/soltar":
            with candado:
                if estado_control(dispositivo) == "tuyo":
                    cambiar_dueno(None)
                control = estado_control(dispositivo)
                quien = nombre_dueno
            self.json(200, {"control": control, "quien": quien})
        elif ruta.startswith("/enviar/"):
            comando = ruta.rsplit("/", 1)[-1]
            if comando not in COMANDOS_VALIDOS:
                return self.json(400, {"ok": False, "error": "Comando invalido"})
            with candado:
                control = estado_control(dispositivo)
                quien = nombre_dueno
                if control == "tuyo":
                    respuesta, error = enviar_seguro(comando)
            if control != "tuyo":
                return self.json(403, {"ok": False, "control": control, "quien": quien,
                                       "error": "No tienes el control"})
            if error:
                self.json(500, {"ok": False, "control": control, "error": error})
            elif respuesta:
                self.json(200, {"ok": True, "control": control, "enviado": comando,
                                "respuesta": respuesta})
            else:
                self.json(200, {"ok": False, "control": control, "enviado": comando,
                                "error": "El ESP32 no respondio (timeout)"})
        else:
            self.responder(404, b"No encontrado", "text/plain")

    def log_request(self, code="-", size="-"):
        if not self.path.startswith("/estado"):  # la pagina consulta /estado cada segundo
            super().log_request(code, size)

    def json(self, codigo, datos):
        self.responder(codigo, json.dumps(datos).encode(), "application/json")

    def responder(self, codigo, cuerpo, tipo):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


if __name__ == "__main__":
    try:
        conectar()
    except Exception as e:
        print(f"Aviso: {e}. Se reintentara al presionar un boton.")
    print(f"Pagina en http://localhost:{PUERTO_WEB}")
    ThreadingHTTPServer(("0.0.0.0", PUERTO_WEB), Manejador).serve_forever()
