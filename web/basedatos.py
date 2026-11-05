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
from pathlib import Path

ARCHIVO = Path(__file__).parent / "camilla.db"
VUELTAS = 300_000  # PBKDF2: ~0.4 s en la Raspberry, frena a quien intente adivinar
ROLES = {"admin": "Administrador", "fisio": "Fisioterapeuta"}
CLAVE_MINIMA = 6
EDAD_MAXIMA = 120

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
CREATE TABLE IF NOT EXISTS pacientes (
    id         INTEGER PRIMARY KEY,
    nombre     TEXT NOT NULL,
    edad       INTEGER NOT NULL,
    creado     TEXT NOT NULL,
    creado_por TEXT NOT NULL
);
"""


def abrir():
    con = sqlite3.connect(ARCHIVO, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def iniciar():
    """Crea la base si no existe, solo legible por el dueno (tiene datos de pacientes)."""
    ARCHIVO.touch(mode=0o600, exist_ok=True)
    with closing(abrir()) as con, con:
        con.executescript(TABLAS)


def ahora():
    return time.strftime("%Y-%m-%d %H:%M")


def cifrar(clave, sal):
    return hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), VUELTAS).hex()


def limpiar(texto, largo):
    """Sin espacios de mas y con un largo maximo."""
    return " ".join(str(texto or "").split())[:largo]


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


def guardar_paciente(id_paciente, nombre, edad, quien):
    """Nuevo (id None) o editado. Devuelve (id, None) o (None, (campo, mensaje))."""
    nombre = limpiar(nombre, 80)
    if len(nombre) < 2:
        return None, ("nombre", "Escribe el nombre del paciente.")
    if isinstance(edad, bool) or not isinstance(edad, int) or not 0 <= edad <= EDAD_MAXIMA:
        return None, ("edad", f"La edad debe ser un número entre 0 y {EDAD_MAXIMA}.")
    with closing(abrir()) as con, con:
        if id_paciente is None:
            return con.execute("INSERT INTO pacientes (nombre, edad, creado, creado_por) VALUES (?, ?, ?, ?)",
                               (nombre, edad, ahora(), quien)).lastrowid, None
        if con.execute("UPDATE pacientes SET nombre = ?, edad = ? WHERE id = ?",
                       (nombre, edad, id_paciente)).rowcount == 1:
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
