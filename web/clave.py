#!/usr/bin/env python3
"""Contrasena del panel de la camilla: una sola, la misma para todos.

El nombre del inicio de sesion solo sirve para ver quien tiene el control;
la contrasena evita que entre cualquiera que este en la red.
Se guarda cifrada (PBKDF2) en clave.json, al lado de este archivo. Ese archivo
NO se sube a git (esta en .gitignore): el repo es publico.

Uso:  python3 clave.py      (pide la nueva contrasena dos veces)
El servidor la lee en cada inicio de sesion: no hace falta reiniciarlo.
"""
import getpass
import hashlib
import hmac
import json
import secrets
import sys
from pathlib import Path

ARCHIVO = Path(__file__).parent / "clave.json"
VUELTAS = 300_000  # mas vueltas = mas lento adivinarla (unos 0,4 s por intento en la Raspberry)
MINIMO = 6


def cifrar(clave, sal):
    return hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), VUELTAS).hex()


def hay_clave():
    return ARCHIVO.exists()


def guardar(clave):
    sal = secrets.token_hex(16)
    ARCHIVO.touch(mode=0o600)  # solo tu usuario puede leerlo
    ARCHIVO.write_text(json.dumps({"sal": sal, "clave": cifrar(clave, sal)}, indent=2) + "\n")


def comprobar(clave):
    """True si la contrasena es la del panel."""
    try:
        guardada = json.loads(ARCHIVO.read_text())
    except FileNotFoundError:
        return False  # sin contrasena puesta no entra nadie
    return hmac.compare_digest(cifrar(clave, guardada["sal"]), guardada["clave"])


if __name__ == "__main__":
    nueva = getpass.getpass(f"Nueva contrasena del panel (minimo {MINIMO} caracteres): ")
    if len(nueva) < MINIMO:
        sys.exit("Muy corta. No se cambio nada.")
    if getpass.getpass("Repitela: ") != nueva:
        sys.exit("No coinciden. No se cambio nada.")
    guardar(nueva)
    print("Contrasena cambiada. Ya vale para los proximos inicios de sesion.")
