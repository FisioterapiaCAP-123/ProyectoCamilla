import json
import re
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import basedatos
import excel
import hardware
import paginas
import reloj

PUERTO_WEB = 8000
IP_RED = "10.42.0.1"  # IP de la Raspberry en su propia red WiFi "Camilla"
TIEMPO_LIBERAR = 10  # segundos sin noticias de quien tiene el control para liberarlo (la pagina consulta cada 1 s)
ESPERA_SOLICITUD = 35  # segundos que dura un pedido de control sin respuesta (las paginas cuentan 30)
HOMBRE_MUERTO = 1.0  # segundos sin "mover" para parar un motor continuo (la pagina lo repite mientras se mantiene el boton)
SESION_HORAS = 12  # una sesion que no se usa en este tiempo se borra
IP_RECORDADA = 60 * 60  # el reparto de IP de la red Camilla dura 60 min: antes nadie mas puede tener esa IP
PRUEBAS_INTERNET = ("/generate_204", "/gen_204")  # rutas con que Android pregunta si hay internet
LIMITES = {"cabeza": (-30, 70), "piernas": (0, 45)}  # grados: iguales a CONFIG en publico/js/config.js
SECCIONES = ("altura", "cabeza", "piernas")

# Manuales en PDF (web/manuales/). Se leen en cada descarga: para cambiar uno basta con reemplazar el archivo
CARPETA_MANUALES = Path(__file__).parent / "manuales"
MANUALES = {  # tipo -> (archivo, quien lo puede bajar)
    "usuario": ("manual-usuario.pdf", ("fisio", "admin")),
    "tecnico": ("manual-tecnico.pdf", ("admin",)),
}

# PIN del equipo recordado: en la tablet, Registros y Usuarios se abren con PIN y se cierran
# solos sin uso. La pagina cierra a los 30 min; el servidor da 1 min mas de margen
REGISTROS_ABIERTO = 31 * 60  # segundos que siguen abiertos desde la ultima actividad
PIN_INTENTOS = 5  # intentos fallidos antes de esperar
PIN_ESPERA = 60  # segundos de espera; se duplica en cada tanda fallida (hasta 1 h)


def duracion(segundos):
    """60 -> '1 minuto', 3600 -> '1 hora', 45 -> '45 segundos': para los avisos."""
    for unidad, nombre in ((3600, "hora"), (60, "minuto")):
        if segundos >= unidad:
            n = round(segundos / unidad)
            return f"{n} {nombre}{'s' if n != 1 else ''}"
    return f"{int(segundos)} segundo{'s' if int(segundos) != 1 else ''}"


def con_pin(sesion):
    """Registros y Usuarios piden PIN en un equipo recordado de un administrador."""
    return bool(sesion["llave"]) and sesion["rol"] == "admin"


# Lo que ve una pagina cuya sesion cerro otro (los motivos son los de Camilla.cerrar)
AVISOS_CIERRE = {
    "entro desde otro dispositivo": "Tu perfil se abrió en otro equipo o pestaña.",
    "perfil desactivado": "Tu perfil fue desactivado. Habla con el administrador.",
    "perfil borrado": "Tu perfil fue borrado.",
}

LARGO_JSON = 4096  # bytes que se aceptan en una peticion
LARGO_EXCEL = 64 * 1024  # la descarga de Excel manda la lista de registros que se ven (hasta ~9000)

SILENCIO = ("/api/estado", "/api/mover", "/api/paso", "/vendor/", "/css/", "/js/")  # se piden muy seguido: no se anotan en el registro

candado = threading.Lock()  # una cosa a la vez: todo el estado de la camilla


def anotar(texto):
    """Mensaje al registro (la terminal, o journalctl -t python3 con la red encendida)."""
    print(reloj.texto("[%d/%b/%Y %H:%M:%S]"), texto, file=sys.stderr, flush=True)


class Camilla:
    """Estado compartido por todas las paginas. Cada metodo se llama con `candado` tomado."""

    def __init__(self):
        self.sesiones = {}  # token -> {"id", "usuario", "nombre", "rol", "visto", "llave", "ip"}: el perfil de cada pagina
        # token -> (aviso, momento) de las sesiones que cerro otro: la pagina sabe por que salio
        # y un equipo recordado no vuelve a entrar solo (dos pestanas se sacarian entre si sin parar)
        self.cerradas = {}
        # huella de la llave -> {"fallos", "tandas", "espera"}: va por equipo y no por sesion,
        # asi recargar la pagina no da intentos nuevos
        self.intentos_pin = {}
        self.titular = None  # usuario de quien tiene el control (None = libre)
        self.solicitud = None  # pedido de control pendiente: {"id", "usuario", "nombre", "token", "creada"}
        self.respuestas = {}  # token de quien pidio el control -> {"aceptada", "usuario"}: se entrega una vez
        self.paro = False  # paro de emergencia: lo puede activar o liberar cualquiera
        self.angulos = {"cabeza": 0, "piernas": 0}  # posicion simulada mientras no haya sensores
        self.motor = None  # motor continuo en marcha: {"seccion", "dir", "visto"}
        self.hardware = hardware.Simulador()  # al arrancar, servidor.py pone aqui el ESP32

    # ---------- sesiones ----------
    def entrar(self, perfil, huella_llave=None, con_clave=True, pin=False):
        """Nueva sesion para ese perfil (ya se comprobo su contrasena o la llave del equipo).

        Un perfil tiene una sola sesion: si ya estaba abierto en otro celular o
        pestana, esa se cierra. El control no pasa solo al nuevo dispositivo.
        huella_llave: la del equipo recordado, para anularla si sale con "Salir".
        con_clave: entro con contrasena (no con la llave): Registros empieza abierto y puede crear el PIN.
        pin: el equipo ya tiene PIN."""
        for viejo in [t for t, s in self.sesiones.items() if s["id"] == perfil["id"]]:
            self.cerrar(viejo, "entro desde otro dispositivo")
        token = secrets.token_urlsafe(24)
        ahora = time.monotonic()
        self.sesiones[token] = {"id": perfil["id"], "usuario": perfil["usuario"], "nombre": perfil["nombre"],
                                "rol": perfil["rol"], "visto": ahora, "llave": huella_llave, "ip": None,
                                "con_clave": con_clave, "pin": pin,
                                "abierto_hasta": ahora + REGISTROS_ABIERTO if con_clave else 0.0}
        anotar(f"{perfil['usuario']} inicio sesion")
        return token

    def sesion_de(self, token, ip=None):
        """La sesion (perfil) de ese token, o None. De paso anota que esa pagina sigue viva y desde que IP."""
        sesion = self.sesiones.get(token) if token else None
        if sesion is not None:
            sesion["visto"] = time.monotonic()
            sesion["ip"] = ip
        return sesion

    def es_equipo_recordado(self, ip):
        """Esa IP es de un equipo recordado (la tablet de control) que se uso hace poco."""
        t = time.monotonic()
        return any(s["llave"] and s["ip"] == ip and t - s["visto"] < IP_RECORDADA for s in self.sesiones.values())

    def cerrar(self, token, motivo):
        usuario = self.sesiones[token]["usuario"]
        self.respuestas.pop(token, None)
        if self.solicitud and self.solicitud["token"] == token:
            self.solicitud = None
        anotar(f"{usuario} cerro sesion ({motivo})")
        if motivo in AVISOS_CIERRE:
            self.cerradas[token] = (AVISOS_CIERRE[motivo], time.monotonic())
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
            return False, f"{self.solicitud['nombre']} ya solicitó el control. Intenta de nuevo en unos segundos."
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
            # sesion cerrada por otro (otro equipo, perfil desactivado o borrado): por que
            "cerrada": self.cerradas[token][0] if not usuario and token in self.cerradas else None,
            # equipo recordado de un administrador: Registros y Usuarios van con PIN
            "registros": ({"pin": sesion["pin"], "abierto": time.monotonic() < sesion["abierto_hasta"],
                           "pide_clave": not sesion["con_clave"]}
                          if sesion and con_pin(sesion) else None),
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
        for token in [k for k, (_, cuando) in self.cerradas.items() if t - cuando > SESION_HORAS * 3600]:
            del self.cerradas[token]


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
        guardado, error = basedatos.guardar_paciente(id_paciente, datos, admin["usuario"])
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
        # Excepcion: a la tablet de control se le dice que si hay internet (204). Si no, Android
        # muestra "sin internet" todo el tiempo. Solo a ella: un celular que lo creyera dejaria
        # de usar sus datos moviles mientras esta en la red Camilla.
        host = (self.headers.get("Host") or "").split(":")[0]
        ruta = urlsplit(self.path).path
        if self.connection.getsockname()[0] == IP_RED and host != IP_RED:
            if ruta in PRUEBAS_INTERNET:
                with candado:
                    recordado = camilla.es_equipo_recordado(self.client_address[0])
                if recordado:
                    return self.responder(204, b"", "text/plain")
            self.send_response(302)
            self.send_header("Location", f"http://{IP_RED}:{PUERTO_WEB}/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if ruta == "/api/estado":
            token = self.headers.get("X-Sesion", "")
            with candado:
                datos = camilla.estado(camilla.sesion_de(token, self.client_address[0]), token)
            self.json(200, datos)
        elif ruta == "/":
            self.responder(200, *paginas.pagina())
        elif archivo := paginas.archivo_publico(ruta):
            self.responder(200, *archivo)
        else:
            self.responder(404, b"No encontrado", "text/plain")

    def do_POST(self):
        ruta = urlsplit(self.path).path
        datos = self.leer_json(LARGO_EXCEL if ruta == "/api/pacientes/excel" else LARGO_JSON)
        if datos is None:
            return self.json(400, {"ok": False, "mensaje": "Petición inválida."})
        if ruta == "/api/login":
            return self.login(datos)
        if ruta == "/api/registro":
            return self.registro(datos)
        if ruta == "/api/reanudar":
            return self.reanudar(datos)

        token = self.headers.get("X-Sesion", "")
        llave_salida = None
        with candado:
            sesion = camilla.sesion_de(token, self.client_address[0])
            perfil = dict(sesion) if sesion else None  # copia: la base de datos se usa sin el candado
            if ruta == "/api/paro":  # el paro lo puede mandar cualquiera, aunque no haya iniciado sesion
                ok, mensaje = camilla.cambiar_paro(datos.get("activo") is True,
                                                   sesion["usuario"] if sesion else f"alguien en {self.client_address[0]}")
            elif sesion is None:
                return self.json(401, {"ok": False, "mensaje": "Tu sesión terminó. Vuelve a iniciar sesión."})
            elif ruta == "/api/logout":
                ok, mensaje = True, None
                llave_salida = sesion["llave"]  # salir a proposito: el equipo deja de entrar solo
                camilla.cerrar(token, "salio")
            elif ruta in ACCIONES:
                ok, mensaje = ACCIONES[ruta](camilla, datos, sesion, token)
            elif ruta in ("/api/manual", "/api/pin/abrir", "/api/pin/crear", "/api/pin/cerrar", "/api/pin/seguir"):
                ok = None  # el archivo y el PIN se leen fuera del candado
            elif not ruta.startswith(("/api/pacientes/", "/api/usuarios/")):
                return self.responder(404, b"No encontrado", "text/plain")
            elif perfil["rol"] != "admin":
                return self.json(403, {"ok": False, "mensaje": "Solo un administrador puede entrar aquí."})
            elif con_pin(sesion) and time.monotonic() >= sesion["abierto_hasta"]:
                return self.json(200, {"ok": False, "bloqueado": True, "mensaje": "Registros está bloqueado. Ingresa tu PIN."})
            else:
                ok = None
                if con_pin(sesion):  # se usa: sigue abierto
                    sesion["abierto_hasta"] = time.monotonic() + REGISTROS_ABIERTO
        if ok is None:
            if ruta == "/api/manual":
                return self.manual(datos, perfil)
            if ruta.startswith("/api/pin/"):
                return self.pin(ruta, datos, sesion)
            if ruta == "/api/pacientes/excel":
                return self.excel(datos, perfil)
            respuesta = administrar(ruta, datos, perfil)
            if respuesta is None:
                return self.responder(404, b"No encontrado", "text/plain")
            return self.json(200, respuesta)
        if llave_salida:
            basedatos.borrar_llave(llave_salida)
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
        self.ajustar_hora(datos, perfil)
        # "Recordar este equipo": llave nueva. Sin marcarlo se anulan las de otros equipos:
        # el perfil paso a este, y la tablet no debe volver a entrar sola y sacarlo
        if datos.get("recordar") is True:
            llave = basedatos.crear_llave(perfil["id"])
            self.abrir_sesion(perfil, llave)
        else:
            basedatos.borrar_llaves(perfil["id"])
            self.abrir_sesion(perfil)

    def reanudar(self, datos):
        """Equipo recordado (la tablet de control): vuelve a entrar con su llave, sin contrasena.
        Pasa si Android cerro la pestana o si se reinicio la Raspberry."""
        llave = datos.get("llave")
        perfil = basedatos.usar_llave(llave)
        if perfil is None:
            return self.json(200, {"ok": False, "mensaje": "Este equipo ya no está recordado. Inicia sesión."})
        self.ajustar_hora(datos, perfil)  # despues de un reinicio de la Raspberry, el primero en llegar suele ser la tablet
        anotar(f"{perfil['usuario']} volvio a entrar (equipo recordado)")
        self.abrir_sesion(perfil, llave, nueva=False)

    def registro(self, datos):
        # Cualquiera puede crear su perfil: entra como fisioterapeuta
        perfil, error = basedatos.crear_usuario(datos.get("usuario"), datos.get("nombre"), datos.get("clave"))
        if error:
            return self.json(200, {"ok": False, "campo": error[0], "mensaje": error[1]})
        self.ajustar_hora(datos, perfil)
        anotar(f"{perfil['usuario']} creo su perfil")
        self.abrir_sesion(perfil)

    def ajustar_hora(self, datos, perfil):
        """La Raspberry no tiene reloj propio: toma la hora del equipo que entra (ver reloj.py)."""
        corregido = reloj.ajustar(datos.get("hora"))
        if corregido is not None:
            anotar(f"hora de la camilla corregida {corregido:+.0f} s con el equipo de {perfil['usuario']}")

    def abrir_sesion(self, perfil, llave=None, nueva=True):
        """llave: la del equipo recordado. Si es nueva se le entrega a la pagina para que la guarde.
        nueva=False: entro con la llave (sin contrasena), y Registros empieza cerrado."""
        huella = basedatos.huella(llave) if llave else None
        pin = basedatos.tiene_pin(huella) if huella and not nueva else False
        with candado:
            token = camilla.entrar(perfil, huella, con_clave=nueva, pin=pin)
            control = camilla.control()
        respuesta = {"ok": True, "sesion": token, "usuario": perfil["usuario"], "nombre": perfil["nombre"],
                     "rol": perfil["rol"], "control": control}
        if llave and nueva:
            respuesta["llave"] = llave
        self.json(200, respuesta)

    def excel(self, datos, admin):
        """Los registros pedidos (los que se ven en la tabla, en ese orden) como archivo .xlsx."""
        ids = datos.get("ids")
        if not (isinstance(ids, list) and ids and all(es_id(i) for i in ids)):
            return self.json(200, {"ok": False, "mensaje": "No hay registros para descargar."})
        por_id = {p["id"]: p for p in basedatos.pacientes()}
        elegidos = [por_id[i] for i in dict.fromkeys(ids) if i in por_id]
        if not elegidos:
            return self.json(200, {"ok": False, "mensaje": "Esos registros ya no existen."})
        anotar(f"{admin['usuario']} descargo {len(elegidos)} registros de pacientes en Excel")
        nombre = f"registros-{reloj.texto('%Y-%m-%d')}.xlsx"
        self.responder(200, excel.crear(elegidos), excel.TIPO,
                       {"Content-Disposition": f'attachment; filename="{nombre}"', "Cache-Control": "no-store"})

    def pin(self, ruta, datos, sesion):
        """PIN del equipo recordado. `sesion` es la de la camilla (se cambia con el candado tomado).
        abrir {pin}: abre Registros y Usuarios. crear {pin, clave?}: PIN nuevo; pide la contrasena
        si la sesion no entro con ella. cerrar: los cierra ya. seguir: hubo actividad, siguen abiertos."""
        if not con_pin(sesion):
            return self.json(200, {"ok": False, "mensaje": "Este equipo no usa PIN."})
        ahora = time.monotonic()
        if ruta == "/api/pin/cerrar":
            with candado:
                sesion["abierto_hasta"] = 0.0
            return self.json(200, {"ok": True})
        if ruta == "/api/pin/seguir":
            with candado:
                abierto = ahora < sesion["abierto_hasta"]
                if abierto:
                    sesion["abierto_hasta"] = ahora + REGISTROS_ABIERTO
            return self.json(200, {"ok": abierto})
        if ruta not in ("/api/pin/abrir", "/api/pin/crear"):
            return self.responder(404, b"No encontrado", "text/plain")

        pin = str(datos.get("pin", ""))
        if not re.fullmatch(r"\d{4}", pin):
            return self.json(200, {"ok": False, "campo": "pin", "mensaje": "El PIN debe tener 4 dígitos."})
        huella = sesion["llave"]

        if ruta == "/api/pin/crear":
            if not sesion["con_clave"] and basedatos.comprobar(sesion["usuario"], str(datos.get("clave", ""))) is None:
                time.sleep(1)  # frena a quien intente adivinarla
                return self.json(200, {"ok": False, "campo": "clave", "mensaje": "Contraseña incorrecta."})
            if not basedatos.guardar_pin(huella, pin):
                return self.json(200, {"ok": False, "mensaje": "Este equipo ya no está recordado. Vuelve a iniciar sesión."})
            with candado:
                sesion.update(pin=True, abierto_hasta=time.monotonic() + REGISTROS_ABIERTO)
                camilla.intentos_pin.pop(huella, None)
            anotar(f"{sesion['usuario']} creo el PIN de su equipo recordado")
            return self.json(200, {"ok": True})

        with candado:
            intentos = camilla.intentos_pin.setdefault(huella, {"fallos": 0, "tandas": 0, "espera": 0.0})
            if ahora < intentos["espera"]:
                faltan = int(intentos["espera"] - ahora) + 1
                return self.json(200, {"ok": False, "mensaje": f"Demasiados intentos. Intenta de nuevo en {duracion(faltan)}."})
        if not sesion["pin"]:
            return self.json(200, {"ok": False, "sin_pin": True, "mensaje": "Este equipo todavía no tiene PIN."})
        bueno = basedatos.comprobar_pin(huella, pin)  # lento a proposito: fuera del candado
        with candado:
            if bueno:
                camilla.intentos_pin.pop(huella, None)
                sesion["abierto_hasta"] = time.monotonic() + REGISTROS_ABIERTO
                return self.json(200, {"ok": True})
            intentos["fallos"] += 1
            if intentos["fallos"] >= PIN_INTENTOS:
                espera = min(PIN_ESPERA * 2 ** intentos["tandas"], 3600)
                intentos.update(fallos=0, tandas=intentos["tandas"] + 1, espera=time.monotonic() + espera)
                anotar(f"PIN equivocado {PIN_INTENTOS} veces en el equipo de {sesion['usuario']}: espera {espera} s")
                return self.json(200, {"ok": False, "campo": "pin",
                                       "mensaje": f"PIN incorrecto. Demasiados intentos: intenta de nuevo en {duracion(espera)}."})
        return self.json(200, {"ok": False, "campo": "pin", "mensaje": "PIN incorrecto."})

    def manual(self, datos, perfil):
        """Manual en PDF. El de usuario lo baja cualquiera con sesion; el tecnico, solo un administrador."""
        archivo, roles = MANUALES.get(str(datos.get("tipo")), (None, ()))
        if archivo is None:
            return self.json(200, {"ok": False, "mensaje": "Ese manual no existe."})
        if perfil["rol"] not in roles:
            return self.json(403, {"ok": False, "mensaje": "Solo un administrador puede descargar este manual."})
        try:
            contenido = (CARPETA_MANUALES / archivo).read_bytes()
        except OSError:
            return self.json(200, {"ok": False, "mensaje": "Ese manual todavía no está disponible."})
        anotar(f"{perfil['usuario']} descargo el manual {datos['tipo']}")
        self.responder(200, contenido, "application/pdf",
                       {"Content-Disposition": f'attachment; filename="{archivo}"', "Cache-Control": "no-store"})

    def leer_json(self, limite):
        try:
            largo = int(self.headers.get("Content-Length") or 0)
            if largo > limite:
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

    def responder(self, codigo, cuerpo, tipo, cabeceras=None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        if tipo.startswith("application/json"):
            self.send_header("Cache-Control", "no-store")
        for nombre, valor in (cabeceras or {}).items():
            self.send_header(nombre, valor)
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
