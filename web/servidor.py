import json
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import basedatos
import hardware
import paginas

PUERTO_WEB = 8000
IP_RED = "10.42.0.1"  # IP de la Raspberry en su propia red WiFi "Camilla"
TIEMPO_LIBERAR = 10  # segundos sin noticias de quien tiene el control para liberarlo (la pagina consulta cada 1 s)
ESPERA_SOLICITUD = 35  # segundos que dura un pedido de control sin respuesta (las paginas cuentan 30)
HOMBRE_MUERTO = 1.0  # segundos sin "mover" para parar un motor continuo (la pagina lo repite mientras se mantiene el boton)
SESION_HORAS = 12  # una sesion que no se usa en este tiempo se borra
LIMITES = {"cabeza": (-30, 70), "piernas": (0, 45)}  # grados: iguales a CONFIG en publico/js/config.js
SECCIONES = ("altura", "cabeza", "piernas")

SILENCIO = ("/api/estado", "/api/mover", "/api/paso", "/vendor/", "/css/", "/js/")  # se piden muy seguido: no se anotan en el registro

candado = threading.Lock()  # una cosa a la vez: todo el estado de la camilla


def anotar(texto):
    """Mensaje al registro (la terminal, o journalctl -t python3 con la red encendida)."""
    print(time.strftime("[%d/%b/%Y %H:%M:%S]"), texto, file=sys.stderr, flush=True)


class Camilla:
    """Estado compartido por todas las paginas. Cada metodo se llama con `candado` tomado."""

    def __init__(self):
        self.sesiones = {}  # token -> {"id", "usuario", "nombre", "rol", "visto"}: el perfil de cada pagina
        self.titular = None  # usuario de quien tiene el control (None = libre)
        self.solicitud = None  # pedido de control pendiente: {"id", "usuario", "nombre", "token", "creada"}
        self.respuestas = {}  # token de quien pidio el control -> {"aceptada", "usuario"}: se entrega una vez
        self.paro = False  # paro de emergencia: lo puede activar o liberar cualquiera
        self.angulos = {"cabeza": 0, "piernas": 0}  # posicion simulada mientras no haya sensores
        self.motor = None  # motor continuo en marcha: {"seccion", "dir", "visto"}
        self.hardware = hardware.Simulador()  # al arrancar, servidor.py pone aqui el ESP32

    # ---------- sesiones ----------
    def entrar(self, perfil):
        """Nueva sesion para ese perfil (ya se comprobo su contrasena).

        Un perfil tiene una sola sesion: si ya estaba abierto en otro celular o
        pestana, esa se cierra. El control no pasa solo al nuevo dispositivo."""
        for viejo in [t for t, s in self.sesiones.items() if s["id"] == perfil["id"]]:
            self.cerrar(viejo, "entro desde otro dispositivo")
        token = secrets.token_urlsafe(24)
        self.sesiones[token] = {"id": perfil["id"], "usuario": perfil["usuario"], "nombre": perfil["nombre"],
                                "rol": perfil["rol"], "visto": time.monotonic()}
        anotar(f"{perfil['usuario']} inicio sesion")
        return token

    def sesion_de(self, token):
        """La sesion (perfil) de ese token, o None. De paso anota que esa pagina sigue viva."""
        sesion = self.sesiones.get(token) if token else None
        if sesion is not None:
            sesion["visto"] = time.monotonic()
        return sesion

    def cerrar(self, token, motivo):
        usuario = self.sesiones[token]["usuario"]
        self.respuestas.pop(token, None)
        if self.solicitud and self.solicitud["token"] == token:
            self.solicitud = None
        anotar(f"{usuario} cerro sesion ({motivo})")
        if self.titular == usuario:
            self.liberar(f"{usuario} {motivo}")
        del self.sesiones[token]

    def echar(self, id_usuario, motivo):
        """Cierra la sesion de un perfil que se desactivo o se borro."""
        for token in [t for t, s in self.sesiones.items() if s["id"] == id_usuario]:
            self.cerrar(token, motivo)

    def cambiar_rol(self, id_usuario, rol):
        for sesion in self.sesiones.values():
            if sesion["id"] == id_usuario:
                sesion["rol"] = rol

    def nombre_de(self, usuario):
        """Nombre para mostrar de un usuario conectado (si ya no esta, su usuario)."""
        return next((s["nombre"] for s in self.sesiones.values() if s["usuario"] == usuario), usuario)

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
            self.respuestas[pedido["token"]] = {"aceptada": True, "usuario": self.nombre_de(self.titular)}
            self.cambiar_titular(pedido["usuario"], motivo + ", lo habia pedido")
        else:
            self.cambiar_titular(None, motivo)

    def tomar(self, usuario):
        if self.titular not in (None, usuario):
            return False, f"{self.nombre_de(self.titular)} ya tiene el control."
        self.cambiar_titular(usuario, "lo tomo")
        return True, None

    def solicitar(self, usuario, nombre, token):
        if self.titular in (None, usuario):  # libre: el primero que lo pide se lo queda
            return self.tomar(usuario)
        if self.solicitud and self.solicitud["token"] != token:
            return False, f"{self.solicitud['nombre']} ya pidió el control. Intenta en unos segundos."
        self.respuestas.pop(token, None)
        self.solicitud = {"id": secrets.token_hex(4), "usuario": usuario, "nombre": nombre, "token": token,
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
            return False, "Esa solicitud ya no está vigente."
        pedido, self.solicitud = self.solicitud, None
        self.respuestas[pedido["token"]] = {"aceptada": aceptar, "usuario": self.nombre_de(usuario)}
        if aceptar:
            self.cambiar_titular(pedido["usuario"], f"{usuario} se lo paso")
        else:
            anotar(f"{usuario} no le paso el control a {pedido['usuario']}")
        return True, None

    def soltar(self, usuario):
        if self.titular == usuario:
            self.liberar(f"{usuario} lo libero")
        return True, None

    # ---------- movimiento ----------
    def puede_mover(self, usuario, seccion):
        return usuario == self.titular and not self.paro and self.hardware.disponible(seccion)

    def parar_motores(self, motivo):
        if self.motor:
            anotar(f"motor {self.motor['seccion']} parado ({motivo})")
        self.motor = None
        self.hardware.parar()

    def mover(self, usuario, seccion, direccion):
        """Arranca un motor continuo. La pagina repite la orden mientras se mantiene el boton."""
        if not self.puede_mover(usuario, seccion):
            return False, None  # se descarta en silencio
        if not self.motor or (self.motor["seccion"], self.motor["dir"]) != (seccion, direccion):
            anotar(f"{usuario}: {seccion} {'sube' if direccion > 0 else 'baja'}" + (" (simulado)" if self.hardware.simulado else ""))
        self.motor = {"seccion": seccion, "dir": direccion, "visto": time.monotonic()}
        self.hardware.mover(seccion, direccion)
        return True, None

    def detener(self, usuario, seccion):
        if usuario == self.titular and self.motor and self.motor["seccion"] == seccion:
            self.parar_motores(f"{usuario} solto el boton")
        return True, None

    def paso(self, usuario, seccion, grados):
        if not self.puede_mover(usuario, seccion) or seccion not in LIMITES:
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
    def control(self):
        """Quien tiene el control: "titular" es el nombre que se muestra, "usuario" lo identifica."""
        return {"titular": self.nombre_de(self.titular) if self.titular else None, "usuario": self.titular}

    def estado(self, sesion, token):
        usuario = sesion["usuario"] if sesion else None
        return {
            "usuario": usuario,
            "nombre": sesion["nombre"] if sesion else None,
            "rol": sesion["rol"] if sesion else None,
            "control": self.control(),
            "paro": self.paro,
            "simulacion": self.hardware.simulado,
            "hardware": self.hardware.estado(),
            # el pedido de control solo le llega a quien tiene el control
            "solicitud": ({"id": self.solicitud["id"], "usuario": self.solicitud["nombre"]}
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
        if self.motor and not self.hardware.disponible(self.motor["seccion"]):
            self.parar_motores("se perdio la conexion con el ESP32")
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


def orden_vigente(sesion, datos):
    """Las peticiones pueden llegar desordenadas: la pagina las numera y una atrasada no vale."""
    numero = datos.get("n")
    if not es_id(numero):
        return True
    if numero <= sesion.get("orden", 0):
        return False
    sesion["orden"] = numero
    return True


def accion_mover(c, d, s, t):
    movimiento = seccion_y_direccion(d, "dir")
    if not movimiento or not orden_vigente(s, d):
        return False, None
    return c.mover(s["usuario"], *movimiento)


def accion_detener(c, d, s, t):
    orden_vigente(s, d)  # detener nunca se descarta, pero deja atras a los "mover" atrasados
    return c.detener(s["usuario"], d.get("seccion"))


# Rutas POST que necesitan haber iniciado sesion: (camilla, datos, sesion, token) -> (ok, mensaje)
ACCIONES = {
    "/api/control/tomar": lambda c, d, s, t: c.tomar(s["usuario"]),
    "/api/control/solicitar": lambda c, d, s, t: c.solicitar(s["usuario"], s["nombre"], t),
    "/api/control/cancelar": lambda c, d, s, t: c.cancelar(t),
    "/api/control/responder": lambda c, d, s, t: c.responder(s["usuario"], d.get("id"), d.get("aceptar") is True),
    "/api/control/liberar": lambda c, d, s, t: c.soltar(s["usuario"]),
    "/api/mover": accion_mover,
    "/api/paso": lambda c, d, s, t: (c.paso(s["usuario"], *m) if (m := seccion_y_direccion(d, "grados")) else (False, None)),
    "/api/detener": accion_detener,
}


def es_id(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


def administrar(ruta, datos, admin):
    """Rutas de /api/pacientes y /api/usuarios: solo llegan aqui los administradores.
    Devuelve la respuesta, o None si la ruta no existe. Se llama sin `candado` (usa la base de datos)."""
    if ruta == "/api/pacientes/lista":
        return {"ok": True, "pacientes": basedatos.pacientes()}
    if ruta == "/api/pacientes/guardar":
        id_paciente = datos.get("id")
        if id_paciente is not None and not es_id(id_paciente):
            return {"ok": False, "mensaje": "Petición inválida."}
        guardado, error = basedatos.guardar_paciente(id_paciente, datos.get("nombre"), datos.get("edad"), admin["usuario"])
        if error:
            return {"ok": False, "campo": error[0], "mensaje": error[1]}
        # en el registro del sistema no van datos del paciente, solo el numero
        anotar(f"{admin['usuario']} {'edito' if id_paciente else 'agrego'} el registro de paciente #{guardado}")
        return {"ok": True, "id": guardado}
    if ruta == "/api/pacientes/borrar":
        if not (es_id(datos.get("id")) and basedatos.borrar_paciente(datos["id"])):
            return {"ok": False, "mensaje": "Ese registro ya no existe."}
        anotar(f"{admin['usuario']} borro el registro de paciente #{datos['id']}")
        return {"ok": True}
    if ruta == "/api/usuarios/lista":
        return {"ok": True, "usuarios": basedatos.usuarios()}
    if ruta not in ("/api/usuarios/rol", "/api/usuarios/activo", "/api/usuarios/clave", "/api/usuarios/borrar"):
        return None

    perfil = basedatos.buscar_usuario(datos["id"]) if es_id(datos.get("id")) else None
    if perfil is None:
        return {"ok": False, "mensaje": "Ese perfil ya no existe."}
    # El propio perfil no se toca desde aqui: asi siempre queda al menos un administrador
    if perfil["id"] == admin["id"]:
        return {"ok": False, "mensaje": "Tu propio perfil no se puede cambiar desde aquí."}
    if ruta == "/api/usuarios/rol":
        if datos.get("rol") not in basedatos.ROLES:
            return {"ok": False, "mensaje": "Ese rol no existe."}
        basedatos.cambiar_usuario(perfil["id"], rol=datos["rol"])
        with candado:
            camilla.cambiar_rol(perfil["id"], datos["rol"])
        anotar(f"{admin['usuario']} cambio el rol de {perfil['usuario']} a {datos['rol']}")
    elif ruta == "/api/usuarios/activo":
        activo = datos.get("activo") is True
        basedatos.cambiar_usuario(perfil["id"], activo=int(activo))
        if not activo:
            with candado:
                camilla.echar(perfil["id"], "perfil desactivado")
        anotar(f"{admin['usuario']} {'activo' if activo else 'desactivo'} el perfil de {perfil['usuario']}")
    elif ruta == "/api/usuarios/clave":
        clave = str(datos.get("clave", ""))
        if error := basedatos.revisar_clave(clave):
            return {"ok": False, "campo": "clave", "mensaje": error}
        basedatos.cambiar_usuario(perfil["id"], clave=clave)
        anotar(f"{admin['usuario']} cambio la contrasena de {perfil['usuario']}")
    else:
        basedatos.borrar_usuario(perfil["id"])
        with candado:
            camilla.echar(perfil["id"], "perfil borrado")
        anotar(f"{admin['usuario']} borro el perfil de {perfil['usuario']}")
    return {"ok": True}


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
                datos = camilla.estado(camilla.sesion_de(token), token)
            self.json(200, datos)
        elif ruta == "/":
            self.responder(200, *paginas.pagina())
        elif archivo := paginas.archivo_publico(ruta):
            self.responder(200, *archivo)
        else:
            self.responder(404, b"No encontrado", "text/plain")

    def do_POST(self):
        ruta = urlsplit(self.path).path
        datos = self.leer_json()
        if datos is None:
            return self.json(400, {"ok": False, "mensaje": "Peticion invalida."})
        if ruta == "/api/login":
            return self.login(datos)
        if ruta == "/api/registro":
            return self.registro(datos)

        token = self.headers.get("X-Sesion", "")
        with candado:
            sesion = camilla.sesion_de(token)
            perfil = dict(sesion) if sesion else None  # copia: la base de datos se usa sin el candado
            if ruta == "/api/paro":  # el paro lo puede mandar cualquiera, aunque no haya iniciado sesion
                ok, mensaje = camilla.cambiar_paro(datos.get("activo") is True,
                                                   sesion["usuario"] if sesion else f"alguien en {self.client_address[0]}")
            elif sesion is None:
                return self.json(401, {"ok": False, "mensaje": "Tu sesión terminó. Vuelve a iniciar sesión."})
            elif ruta == "/api/logout":
                ok, mensaje = True, None
                camilla.cerrar(token, "salio")
            elif ruta in ACCIONES:
                ok, mensaje = ACCIONES[ruta](camilla, datos, sesion, token)
            elif not ruta.startswith(("/api/pacientes/", "/api/usuarios/")):
                return self.responder(404, b"No encontrado", "text/plain")
            elif perfil["rol"] != "admin":
                return self.json(403, {"ok": False, "mensaje": "Solo un administrador puede entrar aquí."})
            else:
                ok = None
        if ok is None:
            respuesta = administrar(ruta, datos, perfil)
            if respuesta is None:
                return self.responder(404, b"No encontrado", "text/plain")
            return self.json(200, respuesta)
        self.json(200, {"ok": ok, "mensaje": mensaje})

    def login(self, datos):
        usuario, clave = str(datos.get("usuario", "")).strip(), str(datos.get("clave", ""))
        if not usuario or not clave:
            return self.json(200, {"ok": False, "mensaje": "Escribe tu usuario y tu contraseña."})
        perfil = basedatos.comprobar(usuario, clave)  # lento a proposito: fuera del candado
        if perfil is None:
            time.sleep(1)  # frena a quien intente adivinarla
            anotar(f"contrasena incorrecta (usuario {usuario[:30]!r})")
            return self.json(200, {"ok": False, "mensaje": "Usuario o contraseña incorrectos."})
        if not perfil["activo"]:
            return self.json(200, {"ok": False, "mensaje": "Tu perfil está desactivado. Habla con el administrador."})
        self.abrir_sesion(perfil)

    def registro(self, datos):
        # Cualquiera puede crear su perfil: entra como fisioterapeuta
        perfil, error = basedatos.crear_usuario(datos.get("usuario"), datos.get("nombre"), datos.get("clave"))
        if error:
            return self.json(200, {"ok": False, "campo": error[0], "mensaje": error[1]})
        anotar(f"{perfil['usuario']} creo su perfil")
        self.abrir_sesion(perfil)

    def abrir_sesion(self, perfil):
        with candado:
            token = camilla.entrar(perfil)
            control = camilla.control()
        self.json(200, {"ok": True, "sesion": token, "usuario": perfil["usuario"], "nombre": perfil["nombre"],
                        "rol": perfil["rol"], "control": control})

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
        # una peticion ilegible (por ejemplo HTTPS a este puerto) todavia no tiene self.path
        if not urlsplit(getattr(self, "path", "")).path.startswith(SILENCIO):  # la pagina consulta /api/estado cada segundo
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
    paginas.pagina()  # si falta un parcial, que falle aqui y no con la primera visita
    basedatos.iniciar()
    if not basedatos.hay_admin():
        print("Aviso: no hay administrador. Crea tu perfil en la pagina y luego:  python3 web/basedatos.py admin TU_USUARIO")
    camilla.hardware = hardware.Simulador() if "--simulador" in sys.argv else hardware.Esp32Serial(anotar)
    camilla.hardware.iniciar()
    threading.Thread(target=vigilar, daemon=True).start()
    print(f"Pagina en http://localhost:{PUERTO_WEB}" + (" (simulador: no mueve motores)" if camilla.hardware.simulado else ""))
    ThreadingHTTPServer(("0.0.0.0", PUERTO_WEB), Manejador).serve_forever()
