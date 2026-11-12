#!/usr/bin/env python3
"""Perfiles de usuario y registros de pacientes, en una base SQLite (camilla.db).

Cada persona crea su perfil en la pagina (usuario + contrasena) y entra como
fisioterapeuta. Solo un administrador ve los registros de pacientes y maneja
los perfiles. El primer administrador se nombra desde la terminal.

camilla.db queda al lado de este archivo y NO se sube a git (esta en
.gitignore): tiene datos de pacientes y el repo es publico.

Uso:
  python3 basedatos.py                  lista los perfiles
  python3 basedatos.py admin USUARIO    le da el rol de administrador
  python3 basedatos.py clave USUARIO    le pone una contrasena nueva
"""
import getpass
import hashlib
import hmac
import re
import secrets
import sqlite3
import sys
import time
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

ARCHIVO = Path(__file__).parent / "camilla.db"
VUELTAS = 300_000  # PBKDF2: ~0.4 s en la Raspberry, frena a quien intente adivinar
ROLES = {"admin": "Administrador", "fisio": "Fisioterapeuta"}
CLAVE_MINIMA = 6
EDAD_MAXIMA = 120  # anos: limita la fecha de nacimiento

# Reglas de los campos del paciente. Iguales en vistas/pacientes.js
TEXTOS = {"nombres": 60, "apellidos": 60, "carne": 20, "correo": 100,
          "emergencia_nombre": 80, "fisioterapeuta": 80}  # largo maximo
PARRAFOS = {"diagnostico": 1000, "notas": 2000}  # respetan los saltos de linea
TELEFONOS = ("telefono", "emergencia_telefono")  # 8 numeros de Guatemala
SEXOS = {"F": "Femenino", "M": "Masculino"}
MEDIDAS = {  # (minimo, maximo, decimales, aviso)
    "estatura": (0.3, 2.5, 2, "La estatura va de 0.30 a 2.50 m."),
    "peso": (1, 900, 1, "El peso va de 1 a 900 lb."),
    "dolor": (0, 10, 0, "El dolor es un número entero de 0 a 10."),  # escala EVA: 0 = sin dolor
}

TABLAS = """
CREATE TABLE IF NOT EXISTS usuarios (
    id      INTEGER PRIMARY KEY,
    usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nombre  TEXT NOT NULL,
    rol     TEXT NOT NULL DEFAULT 'fisio' CHECK (rol IN ('admin', 'fisio')),
    activo  INTEGER NOT NULL DEFAULT 1,
    sal     TEXT NOT NULL,
    clave   TEXT NOT NULL,
    creado  TEXT NOT NULL
);
"""
# Todos los campos del paciente son opcionales (vacio = NULL)
TABLA_PACIENTES = """
CREATE TABLE IF NOT EXISTS pacientes (
    id                  INTEGER PRIMARY KEY,
    nombres             TEXT,
    apellidos           TEXT,
    sexo                TEXT,     -- F o M
    nacimiento          TEXT,     -- AAAA-MM-DD
    dpi                 TEXT,     -- 13 numeros
    carne               TEXT,
    telefono            TEXT,     -- 8 numeros
    correo              TEXT,
    emergencia_nombre   TEXT,
    emergencia_telefono TEXT,
    estatura            REAL,     -- metros
    peso                REAL,     -- libras
    fisioterapeuta      TEXT,
    diagnostico         TEXT,
    dolor               INTEGER,  -- 0 a 10
    proxima_cita        TEXT,     -- AAAA-MM-DD HH:MM (24 h)
    notas               TEXT,
    creado              TEXT NOT NULL,
    creado_por          TEXT NOT NULL
)"""
TABLAS += TABLA_PACIENTES + ";"
# Columnas que llena el formulario. Nombres fijos: nunca vienen del usuario
CAMPOS_PACIENTE = ("nombres", "apellidos", "sexo", "nacimiento", "dpi", "carne", "telefono", "correo",
                   "emergencia_nombre", "emergencia_telefono", "estatura", "peso", "fisioterapeuta",
                   "diagnostico", "dolor", "proxima_cita", "notas")


def abrir():
    con = sqlite3.connect(ARCHIVO, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def iniciar():
    """Crea la base si no existe, solo legible por el dueno (tiene datos de pacientes)."""
    ARCHIVO.touch(mode=0o600, exist_ok=True)
    with closing(abrir()) as con, con:
        con.executescript(TABLAS)
    with closing(abrir()) as con:
        migrar_pacientes(con)


def migrar_pacientes(con):
    """Bases de antes del 12-11: pacientes tenia solo nombre y edad, obligatorios.
    Se rehace la tabla con los campos nuevos: el nombre se parte en nombres y apellidos
    (se corrige al editar) y la edad pasa a las notas para no perderla."""
    if "edad" not in {c["name"] for c in con.execute("PRAGMA table_info(pacientes)")}:
        return
    viejos = con.execute("SELECT * FROM pacientes").fetchall()
    con.execute("BEGIN")  # todo o nada
    con.execute(TABLA_PACIENTES.replace("IF NOT EXISTS pacientes", "pacientes_nueva"))
    for f in viejos:
        con.execute("INSERT INTO pacientes_nueva (id, nombres, apellidos, notas, creado, creado_por) VALUES (?, ?, ?, ?, ?, ?)",
                    (f["id"], *partir_nombre(f["nombre"]), f"Edad al registrarlo: {f['edad']} años",
                     f["creado"], f["creado_por"]))
    con.execute("DROP TABLE pacientes")
    con.execute("ALTER TABLE pacientes_nueva RENAME TO pacientes")
    con.commit()


def partir_nombre(completo):
    """'Maria Jose Lopez Garcia' -> ('Maria Jose', 'Lopez Garcia'). Con 2 o 3 palabras solo la primera es nombre."""
    palabras = limpiar(completo, 120).split()
    corte = 2 if len(palabras) >= 4 else 1
    return " ".join(palabras[:corte]) or None, " ".join(palabras[corte:]) or None


def ahora():
    return time.strftime("%Y-%m-%d %H:%M")


def cifrar(clave, sal):
    return hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), VUELTAS).hex()


def limpiar(texto, largo):
    """Sin espacios de mas y con un largo maximo."""
    return " ".join(str(texto or "").split())[:largo]


def limpiar_parrafos(texto, largo):
    """Como limpiar, pero respeta los saltos de linea (a lo mas una linea en blanco seguida)."""
    lineas = (" ".join(linea.split()) for linea in str(texto or "").splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()[:largo]


def leer_fecha(texto, formato):
    try:
        return datetime.strptime(texto, formato)
    except ValueError:
        return None


def publico(fila):
    """Lo que se puede mostrar de un perfil (sin la contrasena)."""
    return {"id": fila["id"], "usuario": fila["usuario"], "nombre": fila["nombre"],
            "rol": fila["rol"], "activo": bool(fila["activo"]), "creado": fila["creado"]}


# ---------- perfiles ----------
def revisar_clave(clave):
    if not re.fullmatch(r"[A-Za-z0-9]*", clave):  # sin tildes, ñ, simbolos ni espacios (igual en index.html)
        return "La contraseña lleva solo letras y números, sin tildes, símbolos ni espacios."
    if len(clave) < CLAVE_MINIMA:
        return f"La contraseña debe tener al menos {CLAVE_MINIMA} caracteres."
    if len(clave) > 100:
        return "La contraseña es demasiado larga."
    return None


def crear_usuario(usuario, nombre, clave):
    """Perfil nuevo como fisioterapeuta. Devuelve (perfil, None) o (None, (campo, mensaje))."""
    usuario = str(usuario or "").strip().lower()
    nombre = str(nombre or "").strip()
    clave = str(clave or "")
    if not nombre:
        return None, ("nombre", "Escribe tu nombre.")
    if not re.fullmatch(r"[A-Za-z]{2,40}", nombre):  # solo letras: sin numeros, tildes, ñ, simbolos ni espacios (igual en index.html)
        return None, ("nombre", "El nombre debe tener de 2 a 40 letras, sin números, tildes, símbolos ni espacios.")
    if not re.fullmatch(r"[a-z0-9]{3,20}", usuario):  # sin tildes, ñ, simbolos ni espacios (igual en index.html)
        return None, ("usuario", "El usuario debe tener de 3 a 20 caracteres: solo letras y números, sin tildes, símbolos ni espacios.")
    if error := revisar_clave(clave):
        return None, ("clave", error)
    sal = secrets.token_hex(16)
    try:
        with closing(abrir()) as con, con:
            cursor = con.execute(
                "INSERT INTO usuarios (usuario, nombre, sal, clave, creado) VALUES (?, ?, ?, ?, ?)",
                (usuario, nombre, sal, cifrar(clave, sal), ahora()))
            fila = con.execute("SELECT * FROM usuarios WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        return None, ("usuario", "Ese usuario ya existe. Elige otro.")
    return publico(fila), None


def comprobar(usuario, clave):
    """El perfil si el usuario existe y la contrasena es correcta, si no None."""
    with closing(abrir()) as con:
        fila = con.execute("SELECT * FROM usuarios WHERE usuario = ?", (str(usuario or "").strip(),)).fetchone()
    if fila is None:
        cifrar(str(clave), secrets.token_hex(16))  # tarda lo mismo: no se nota si el usuario existe
        return None
    if not hmac.compare_digest(cifrar(str(clave), fila["sal"]), fila["clave"]):
        return None
    return publico(fila)


def usuarios():
    with closing(abrir()) as con:
        return [publico(f) for f in con.execute("SELECT * FROM usuarios ORDER BY nombre COLLATE NOCASE")]


def buscar_usuario(id_usuario):
    with closing(abrir()) as con:
        fila = con.execute("SELECT * FROM usuarios WHERE id = ?", (id_usuario,)).fetchone()
    return publico(fila) if fila else None


def hay_admin():
    with closing(abrir()) as con:
        return con.execute("SELECT 1 FROM usuarios WHERE rol = 'admin' AND activo = 1").fetchone() is not None


def cambiar_usuario(id_usuario, **campos):
    """Cambia rol, activo o clave de un perfil. Devuelve True si existia."""
    if "clave" in campos:
        campos["sal"] = secrets.token_hex(16)
        campos["clave"] = cifrar(campos["clave"], campos["sal"])
    columnas = ", ".join(f"{c} = ?" for c in campos)  # nombres fijos: los pone el servidor, no el usuario
    with closing(abrir()) as con, con:
        return con.execute(f"UPDATE usuarios SET {columnas} WHERE id = ?",
                           (*campos.values(), id_usuario)).rowcount == 1


def borrar_usuario(id_usuario):
    with closing(abrir()) as con, con:
        return con.execute("DELETE FROM usuarios WHERE id = ?", (id_usuario,)).rowcount == 1


# ---------- registros de pacientes ----------
def pacientes():
    with closing(abrir()) as con:
        return [dict(f) for f in con.execute("SELECT * FROM pacientes ORDER BY id DESC")]


def revisar_paciente(datos):
    """Los campos del paciente ya limpios. Todos son opcionales: lo vacio queda None.
    Devuelve (campos, None) o (None, (campo, mensaje)). Reglas iguales en vistas/pacientes.js."""
    campos = {c: limpiar(datos.get(c), largo) for c, largo in TEXTOS.items()}
    campos.update({c: limpiar_parrafos(datos.get(c), largo) for c, largo in PARRAFOS.items()})
    campos["sexo"] = str(datos.get("sexo") or "")
    campos["dpi"] = re.sub(r"[\s-]", "", str(datos.get("dpi") or ""))
    campos["nacimiento"] = str(datos.get("nacimiento") or "").strip()
    campos["proxima_cita"] = str(datos.get("proxima_cita") or "").strip().replace("T", " ")
    campos["correo"] = campos["correo"].lower()

    if campos["sexo"] and campos["sexo"] not in SEXOS:
        return None, ("sexo", "Elige femenino o masculino.")
    if campos["dpi"] and not re.fullmatch(r"\d{13}", campos["dpi"]):
        return None, ("dpi", "El DPI tiene 13 números.")
    for campo in TELEFONOS:
        numero = re.sub(r"[\s-]", "", str(datos.get(campo) or ""))  # la pagina lo manda como 5555 1234
        if numero and not re.fullmatch(r"\d{8}", numero):
            return None, (campo, "El teléfono tiene 8 números.")
        campos[campo] = numero
    if campos["correo"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", campos["correo"]):
        return None, ("correo", "Ese correo no es válido.")
    if campos["nacimiento"]:
        nacio = leer_fecha(campos["nacimiento"], "%Y-%m-%d")
        hoy = date.today()
        if nacio is None:
            return None, ("nacimiento", "Esa fecha no es válida.")
        if nacio.date() > hoy:
            return None, ("nacimiento", "La fecha de nacimiento no puede ser futura.")
        if nacio.year < hoy.year - EDAD_MAXIMA:
            return None, ("nacimiento", f"La fecha de nacimiento es de hace más de {EDAD_MAXIMA} años.")
        campos["nacimiento"] = nacio.strftime("%Y-%m-%d")
    if campos["proxima_cita"]:
        cita = leer_fecha(campos["proxima_cita"], "%Y-%m-%d %H:%M")
        if cita is None:
            return None, ("proxima_cita", "Esa fecha y hora no son válidas.")
        campos["proxima_cita"] = cita.strftime("%Y-%m-%d %H:%M")
    for campo, (minimo, maximo, decimales, aviso) in MEDIDAS.items():
        valor = datos.get(campo)
        if valor is None or valor == "":
            campos[campo] = None
            continue
        if (isinstance(valor, bool) or not isinstance(valor, (int, float)) or not minimo <= valor <= maximo
                or (decimales == 0 and valor != int(valor))):
            return None, (campo, aviso)
        campos[campo] = round(valor, decimales) if decimales else int(valor)
    campos = {c: (v if v != "" else None) for c, v in campos.items()}
    if all(v is None for v in campos.values()):
        return None, (None, "Llena al menos un campo.")
    return campos, None


def guardar_paciente(id_paciente, datos, quien):
    """Nuevo (id None) o editado. Devuelve (id, None) o (None, (campo, mensaje))."""
    campos, error = revisar_paciente(datos)
    if error:
        return None, error
    valores = [campos[c] for c in CAMPOS_PACIENTE]
    with closing(abrir()) as con, con:
        if id_paciente is None:
            columnas = ", ".join((*CAMPOS_PACIENTE, "creado", "creado_por"))
            marcas = ", ".join("?" * (len(CAMPOS_PACIENTE) + 2))
            return con.execute(f"INSERT INTO pacientes ({columnas}) VALUES ({marcas})",
                               (*valores, ahora(), quien)).lastrowid, None
        cambios = ", ".join(f"{c} = ?" for c in CAMPOS_PACIENTE)
        if con.execute(f"UPDATE pacientes SET {cambios} WHERE id = ?", (*valores, id_paciente)).rowcount == 1:
            return id_paciente, None
    return None, (None, "Ese registro ya no existe.")


def borrar_paciente(id_paciente):
    with closing(abrir()) as con, con:
        return con.execute("DELETE FROM pacientes WHERE id = ?", (id_paciente,)).rowcount == 1


# ---------- desde la terminal ----------
def buscar_por_usuario(usuario):
    with closing(abrir()) as con:
        return con.execute("SELECT * FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()


if __name__ == "__main__":
    iniciar()
    orden = sys.argv[1:]
    if not orden:
        for u in usuarios():
            print(f"  {u['usuario']:<20} {ROLES[u['rol']]:<15} {'activo' if u['activo'] else 'desactivado':<12} {u['nombre']}")
        if not hay_admin():
            print("No hay administrador. Crea tu perfil en la pagina y luego:  python3 web/basedatos.py admin TU_USUARIO")
    elif orden[0] == "revisar":  # lo usa encender_red.sh: solo avisa si falta el administrador
        if not hay_admin():
            print("Aviso: no hay administrador. Crea tu perfil en la pagina y luego:  python3 web/basedatos.py admin TU_USUARIO")
    elif len(orden) == 2 and orden[0] in ("admin", "clave"):
        fila = buscar_por_usuario(orden[1])
        if fila is None:
            sys.exit(f"No existe el usuario {orden[1]!r}. Primero se crea el perfil en la pagina.")
        if orden[0] == "admin":
            cambiar_usuario(fila["id"], rol="admin", activo=1)
            print(f"{fila['usuario']} ahora es administrador. Si tenia la pagina abierta, que salga y vuelva a entrar.")
        else:
            clave = getpass.getpass("Contraseña nueva: ")
            if error := revisar_clave(clave):
                sys.exit(error)
            if clave != getpass.getpass("Repítela: "):
                sys.exit("No coinciden. No se cambio nada.")
            cambiar_usuario(fila["id"], clave=clave)
            print("Listo: contraseña cambiada.")
    else:
        sys.exit(__doc__)
