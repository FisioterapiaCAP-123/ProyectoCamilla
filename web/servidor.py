
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

PUERTO_WEB = 8000
IP_RED = "10.42.0.1"  # IP de la Raspberry en su propia red WiFi "Camilla"
TIEMPO_LIBERAR = 60  # segundos sin noticias de la pagina que tiene el control para liberarlo

CARPETA = Path(__file__).parent  # los .html se leen en cada visita: al editarlos basta con recargar la pagina
# Bootstrap guardado en web/bootstrap/: la pagina tiene sus estilos sin internet (en la red Camilla no hay)
ARCHIVOS = {
    "/bootstrap/bootstrap.min.css": "text/css; charset=utf-8",
    "/bootstrap/bootstrap.bundle.min.js": "text/javascript; charset=utf-8",
}

candado = threading.RLock()  # una cosa a la vez: el control
dueno = None  # identificador de la pagina que tiene el control (None = libre)
nombre_dueno = ""  # nombre con el que inicio sesion quien tiene el control
visto = 0.0  # ultima vez que esa pagina se comunico


def cambiar_dueno(nuevo, nombre=""):
    """Cambia quien tiene el control."""
    global dueno, nombre_dueno, visto
    dueno, nombre_dueno, visto = nuevo, nombre, time.monotonic()


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
        elif ruta in ARCHIVOS:
            self.responder(200, (CARPETA / ruta.lstrip("/")).read_bytes(), ARCHIVOS[ruta])
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
    print(f"Pagina en http://localhost:{PUERTO_WEB}")
    ThreadingHTTPServer(("0.0.0.0", PUERTO_WEB), Manejador).serve_forever()
