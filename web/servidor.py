#!/usr/bin/env python3
"""Servidor web sencillo: 3 botones que envian comandos al ESP32 por USB serial
y muestran la respuesta que devuelve el ESP32.

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

import serial

BAUDIOS = 115200
PUERTO_WEB = 8000
IP_RED = "10.42.0.1"  # IP de la Raspberry en su propia red WiFi "Camilla"
TIMEOUT_RESPUESTA = 2  # segundos esperando la respuesta del ESP32
COMANDOS_VALIDOS = {"1", "2", "3"}

HTML = (Path(__file__).parent / "index.html").read_bytes()

esp = None
candado = threading.Lock()


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

        if self.path == "/":
            self.responder(200, HTML, "text/html; charset=utf-8")
        elif self.path.startswith("/enviar/"):
            comando = self.path.rsplit("/", 1)[-1]
            if comando not in COMANDOS_VALIDOS:
                return self.json(400, {"ok": False, "error": "Comando invalido"})
            try:
                respuesta = enviar(comando)
            except Exception as e:
                global esp
                esp = None  # forzar reconexion en el siguiente intento
                return self.json(500, {"ok": False, "error": str(e)})
            if respuesta:
                self.json(200, {"ok": True, "enviado": comando, "respuesta": respuesta})
            else:
                self.json(200, {"ok": False, "enviado": comando,
                                "error": "El ESP32 no respondio (timeout)"})
        else:
            self.responder(404, b"No encontrado", "text/plain")

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
