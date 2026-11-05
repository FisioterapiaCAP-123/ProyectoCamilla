import json
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import clave

PUERTO_WEB = 8000
IP_RED = "10.42.0.1"  # IP de la Raspberry en su propia red WiFi "Camilla"
SIMULACION = True  # no hay motores conectados: las ordenes se revisan y se anotan, pero no mueven nada
TIEMPO_LIBERAR = 10  # segundos sin noticias de quien tiene el control para liberarlo (la pagina consulta cada 1 s)
ESPERA_SOLICITUD = 35  # segundos que dura un pedido de control sin respuesta (las paginas cuentan 30)
HOMBRE_MUERTO = 1.0  # segundos sin "mover" para parar un motor continuo (la pagina lo repite mientras se mantiene el boton)
SESION_HORAS = 12  # una sesion que no se usa en este tiempo se borra
LIMITES = {"cabeza": (-30, 70), "piernas": (0, 45)}  # grados: iguales a CONFIG en index.html
SECCIONES = ("altura", "cabeza", "piernas")

CARPETA = Path(__file__).parent  # los archivos se leen en cada visita: al editarlos basta con recargar la pagina
# Bootstrap y fuentes guardados en web/vendor/: la pagina se ve igual sin internet (en la red Camilla no hay)
ARCHIVOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/vendor/bootstrap.min.css": ("vendor/bootstrap.min.css", "text/css; charset=utf-8"),
    "/vendor/bootstrap.bundle.min.js": ("vendor/bootstrap.bundle.min.js", "text/javascript; charset=utf-8"),
    "/vendor/fuentes.css": ("vendor/fuentes.css", "text/css; charset=utf-8"),
}
for _fuente in (CARPETA / "vendor" / "fuentes").glob("*.woff2"):
    ARCHIVOS["/vendor/fuentes/" + _fuente.name] = ("vendor/fuentes/" + _fuente.name, "font/woff2")
SILENCIO = ("/api/estado", "/api/mover", "/api/paso", "/vendor/")  # se piden muy seguido: no se anotan en el registro

candado = threading.Lock()  # una cosa a la vez: todo el estado de la camilla


def anotar(texto):
    """Mensaje al registro (la terminal, o journalctl -t python3 con la red encendida)."""
    print(time.strftime("[%d/%b/%Y %H:%M:%S]"), texto, file=sys.stderr, flush=True)


class Camilla:
    """Estado compartido por todas las paginas. Cada metodo se llama con `candado` tomado."""

    def __init__(self):
        self.sesiones = {}  # token -> {"usuario", "visto"}: el nombre con el que entro cada pagina
        self.titular = None  # nombre de quien tiene el control (None = libre)
        self.solicitud = None  # pedido de control pendiente: {"id", "usuario", "token", "creada"}
        self.respuestas = {}  # token de quien pidio el control -> {"aceptada", "usuario"}: se entrega una vez
        self.paro = False  # paro de emergencia: lo puede activar o liberar cualquiera
        self.angulos = {"cabeza": 0, "piernas": 0}  # posicion simulada mientras no haya sensores
        self.motor = None  # motor continuo en marcha (altura): {"seccion", "dir", "visto"}

    # ---------- sesiones ----------
    def entrar(self, usuario):
        """Nueva sesion con ese nombre, o None si ya hay alguien conectado con el.

        Los nombres no se repiten: asi nadie puede escribir el nombre de otro para
        quedarse con su control sin pedirlo. Si quien lo usaba lleva mas de
        TIEMPO_LIBERAR sin dar senales, el nombre queda libre y su sesion vieja se borra."""
        mismo = [t for t, s in self.sesiones.items() if s["usuario"].lower() == usuario.lower()]
        if any(time.monotonic() - self.sesiones[t]["visto"] <= TIEMPO_LIBERAR for t in mismo):
            return None
        for viejo in mismo:
            del self.sesiones[viejo]
            self.respuestas.pop(viejo, None)
            if self.solicitud and self.solicitud["token"] == viejo:
                self.solicitud = None
        if self.titular and self.titular.lower() == usuario.lower():
            self.liberar(f"{self.titular} sin conexion")  # el control no pasa al nuevo por llamarse igual
        token = secrets.token_urlsafe(24)
        self.sesiones[token] = {"usuario": usuario, "visto": time.monotonic()}
        anotar(f"{usuario} inicio sesion")
        return token

    def usuario_de(self, token):
        """Usuario de la sesion, o None. De paso anota que esa pagina sigue viva."""
        sesion = self.sesiones.get(token) if token else None
        if sesion is None:
            return None
        sesion["visto"] = time.monotonic()
        return sesion["usuario"]

    def salir(self, token, usuario):
        del self.sesiones[token]
        self.respuestas.pop(token, None)
        if self.solicitud and self.solicitud["token"] == token:
            self.solicitud = None
        anotar(f"{usuario} cerro sesion")
        if self.titular == usuario:
            self.liberar(f"{usuario} salio")

    def ultimo_contacto(self, usuario):
        return max((s["visto"] for s in self.sesiones.values() if s["usuario"] == usuario), default=0.0)

    # ---------- control: una sola persona mueve la camilla ----------
    def cambiar_titular(self, nuevo, motivo):
        if nuevo == self.titular:
            return
        self.parar_motores("cambio de control")  # quien pierde el control no deja nada en marcha
        anotar(f"control: {self.titular or 'nadie'} -> {nuevo or 'nadie'} ({motivo})")
        self.titular = nuevo
        if self.solicitud and self.solicitud["usuario"] == nuevo:
            self.solicitud = None

    def liberar(self, motivo):
        """Deja el control libre; si alguien lo estaba pidiendo, pasa a esa persona."""
        if self.solicitud:
            pedido, self.solicitud = self.solicitud, None
            self.respuestas[pedido["token"]] = {"aceptada": True, "usuario": self.titular}
            self.cambiar_titular(pedido["usuario"], motivo + ", lo habia pedido")
        else:
            self.cambiar_titular(None, motivo)

    def tomar(self, usuario):
        if self.titular not in (None, usuario):
            return False, f"{self.titular} ya tiene el control."
        self.cambiar_titular(usuario, "lo tomo")
        return True, None

    def solicitar(self, usuario, token):
        if self.titular in (None, usuario):  # libre: el primero que lo pide se lo queda
            return self.tomar(usuario)
        if self.solicitud and self.solicitud["token"] != token:
            return False, f"{self.solicitud['usuario']} ya pidio el control. Intenta en unos segundos."
        self.respuestas.pop(token, None)
        self.solicitud = {"id": secrets.token_hex(4), "usuario": usuario, "token": token,
                          "creada": time.monotonic()}
        anotar(f"{usuario} pide el control a {self.titular}")
        return True, None

    def cancelar(self, token):
        if self.solicitud and self.solicitud["token"] == token:
            anotar(f"{self.solicitud['usuario']} cancelo su pedido de control")
            self.solicitud = None
        return True, None

    def responder(self, usuario, id_pedido, aceptar):
        if self.titular != usuario:
            return False, "No tienes el control."
        if not self.solicitud or self.solicitud["id"] != id_pedido:
            return False, "Esa solicitud ya no esta vigente."
        pedido, self.solicitud = self.solicitud, None
        self.respuestas[pedido["token"]] = {"aceptada": aceptar, "usuario": usuario}
        if aceptar:
            self.cambiar_titular(pedido["usuario"], f"{usuario} se lo paso")
        else:
            anotar(f"{usuario} no le paso el control a {pedido['usuario']}")
        return True, None

    def soltar(self, usuario):
        if self.titular == usuario:
            self.liberar(f"{usuario} lo libero")
        return True, None

    # ---------- movimiento (simulado: aqui iran las ordenes a los motores) ----------
    def puede_mover(self, usuario):
        return usuario == self.titular and not self.paro

    def parar_motores(self, motivo):
        if self.motor:
            anotar(f"motor {self.motor['seccion']} parado ({motivo})")
        self.motor = None

    def mover(self, usuario, seccion, direccion):
        """Arranca un motor continuo. La pagina repite la orden mientras se mantiene el boton."""
        if not self.puede_mover(usuario):
            return False, None  # se descarta en silencio
        if not self.motor or (self.motor["seccion"], self.motor["dir"]) != (seccion, direccion):
            anotar(f"{usuario}: {seccion} {'sube' if direccion > 0 else 'baja'}" + (" (simulado)" if SIMULACION else ""))
        self.motor = {"seccion": seccion, "dir": direccion, "visto": time.monotonic()}
        return True, None

    def detener(self, usuario, seccion):
        if self.puede_mover(usuario) and self.motor and self.motor["seccion"] == seccion:
            self.parar_motores(f"{usuario} solto el boton")
        return True, None

    def paso(self, usuario, seccion, grados):
        if not self.puede_mover(usuario) or seccion not in LIMITES:
            return False, None
        minimo, maximo = LIMITES[seccion]
        self.angulos[seccion] = max(minimo, min(maximo, self.angulos[seccion] + grados))
        return True, None

    def cambiar_paro(self, activo, quien):
        if activo != self.paro:
            anotar(f"PARO DE EMERGENCIA {'ACTIVADO' if activo else 'liberado'} por {quien}")
        self.paro = activo
        if activo:
            self.parar_motores("paro de emergencia")
        return True, None

    # ---------- lo que la pagina consulta cada segundo ----------
    def estado(self, usuario, token):
        return {
            "usuario": usuario,
            "control": {"titular": self.titular},
            "paro": self.paro,
            "simulacion": SIMULACION,
            # el pedido de control solo le llega a quien tiene el control
            "solicitud": ({"id": self.solicitud["id"], "usuario": self.solicitud["usuario"]}
                          if self.solicitud and usuario and usuario == self.titular else None),
            # la respuesta solo le llega a quien pidio, una sola vez
            "respuesta": self.respuestas.pop(token, None) if usuario else None,
            "telemetria": dict(self.angulos),
        }

    def vigilar(self):
        """Cada medio segundo: hombre muerto, titular desconectado, pedidos vencidos y sesiones viejas."""
        t = time.monotonic()
        if self.motor and t - self.motor["visto"] > HOMBRE_MUERTO:
            self.parar_motores("se dejo de recibir la senal del boton")
        if self.titular and t - self.ultimo_contacto(self.titular) > TIEMPO_LIBERAR:
            self.liberar(f"{self.titular} sin conexion")
        if self.solicitud and t - self.solicitud["creada"] > ESPERA_SOLICITUD:
            anotar(f"el pedido de control de {self.solicitud['usuario']} vencio")
            self.solicitud = None
        for token in [k for k, s in self.sesiones.items() if t - s["visto"] > SESION_HORAS * 3600]:
            del self.sesiones[token]
            self.respuestas.pop(token, None)


camilla = Camilla()


def vigilar():
    while True:
        time.sleep(0.5)
        with candado:
            camilla.vigilar()


def seccion_y_direccion(datos, campo):
    seccion, valor = datos.get("seccion"), datos.get(campo)
    if seccion not in SECCIONES or valor not in (1, -1) or isinstance(valor, bool):
        return None
    return seccion, valor


# Rutas POST que necesitan haber iniciado sesion: (camilla, datos, usuario, token) -> (ok, mensaje)
ACCIONES = {
    "/api/control/tomar": lambda c, d, u, t: c.tomar(u),
    "/api/control/solicitar": lambda c, d, u, t: c.solicitar(u, t),
    "/api/control/cancelar": lambda c, d, u, t: c.cancelar(t),
    "/api/control/responder": lambda c, d, u, t: c.responder(u, d.get("id"), d.get("aceptar") is True),
    "/api/control/liberar": lambda c, d, u, t: c.soltar(u),
    "/api/mover": lambda c, d, u, t: (c.mover(u, *s) if (s := seccion_y_direccion(d, "dir")) else (False, None)),
    "/api/paso": lambda c, d, u, t: (c.paso(u, *s) if (s := seccion_y_direccion(d, "grados")) else (False, None)),
    "/api/detener": lambda c, d, u, t: c.detener(u, d.get("seccion")),
}


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
        if ruta == "/api/estado":
            token = self.headers.get("X-Sesion", "")
            with candado:
                datos = camilla.estado(camilla.usuario_de(token), token)
            self.json(200, datos)
        elif ruta in ARCHIVOS:
            nombre, tipo = ARCHIVOS[ruta]
            self.responder(200, (CARPETA / nombre).read_bytes(), tipo)
        else:
            self.responder(404, b"No encontrado", "text/plain")

    def do_POST(self):
        ruta = urlsplit(self.path).path
        datos = self.leer_json()
        if datos is None:
            return self.json(400, {"ok": False, "mensaje": "Peticion invalida."})
        if ruta == "/api/login":
            return self.login(datos)

        token = self.headers.get("X-Sesion", "")
        with candado:
            usuario = camilla.usuario_de(token)
            if ruta == "/api/paro":  # el paro lo puede mandar cualquiera, aunque no haya iniciado sesion
                ok, mensaje = camilla.cambiar_paro(datos.get("activo") is True,
                                                   usuario or f"alguien en {self.client_address[0]}")
            elif usuario is None:
                return self.json(401, {"ok": False, "mensaje": "Tu sesion termino. Vuelve a iniciar sesion."})
            elif ruta == "/api/logout":
                ok, mensaje = True, None
                camilla.salir(token, usuario)
            elif ruta in ACCIONES:
                ok, mensaje = ACCIONES[ruta](camilla, datos, usuario, token)
            else:
                return self.responder(404, b"No encontrado", "text/plain")
        self.json(200, {"ok": ok, "mensaje": mensaje})

    def login(self, datos):
        # El nombre solo dice quien tiene el control; la contrasena es una sola para todos
        nombre = " ".join(str(datos.get("usuario", "")).split())[:30]
        if not nombre:
            return self.json(200, {"ok": False, "campo": "usuario", "mensaje": "Escribe tu nombre."})
        if not clave.comprobar(str(datos.get("clave", ""))):  # lento a proposito: fuera del candado
            time.sleep(1)  # frena a quien intente adivinarla
            anotar(f"contrasena incorrecta (nombre {nombre!r})")
            return self.json(200, {"ok": False, "mensaje": "Contraseña incorrecta."})
        with candado:
            token = camilla.entrar(nombre)
            titular = camilla.titular
        if token is None:
            return self.json(200, {"ok": False, "campo": "usuario",
                                   "mensaje": f"Ya hay alguien conectado como {nombre}. Usa otro nombre."})
        self.json(200, {"ok": True, "usuario": nombre, "sesion": token, "control": {"titular": titular}})

    def leer_json(self):
        try:
            largo = int(self.headers.get("Content-Length") or 0)
            if largo > 4096:
                return None
            datos = json.loads(self.rfile.read(largo) or b"{}")
        except ValueError:
            return None
        return datos if isinstance(datos, dict) else None

    def log_request(self, code="-", size="-"):
        if not urlsplit(self.path).path.startswith(SILENCIO):  # la pagina consulta /api/estado cada segundo
            super().log_request(code, size)

    def json(self, codigo, datos):
        self.responder(codigo, json.dumps(datos, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def responder(self, codigo, cuerpo, tipo):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        if tipo.startswith("application/json"):
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)


if __name__ == "__main__":
    if not clave.hay_clave():
        print("Aviso: no hay contrasena del panel y no entra nadie. Ponla con:  python3 web/clave.py")
    threading.Thread(target=vigilar, daemon=True).start()
    print(f"Pagina en http://localhost:{PUERTO_WEB}")
    ThreadingHTTPServer(("0.0.0.0", PUERTO_WEB), Manejador).serve_forever()
