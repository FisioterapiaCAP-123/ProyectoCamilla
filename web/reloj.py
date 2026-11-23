import time
from datetime import date, datetime

TOLERANCIA = 120  # segundos: menos que esto no vale la pena corregir
MINIMA = datetime(2026, 1, 1).timestamp()  # un equipo con hora anterior a esto tiene la hora mal

desfase = 0.0  # segundos que se le suman a la hora de la Raspberry


def marca():
    """Segundos desde 1970, ya corregidos."""
    return time.time() + desfase


def ahora():
    return datetime.fromtimestamp(marca())


def hoy():
    return date.fromtimestamp(marca())


def texto(formato):
    """Como time.strftime, con la hora corregida."""
    return time.strftime(formato, time.localtime(marca()))


def ajustar(ms_equipo):
    global desfase
    if isinstance(ms_equipo, bool) or not isinstance(ms_equipo, (int, float)):
        return None
    equipo = ms_equipo / 1000
    if equipo < MINIMA:
        return None
    diferencia = equipo - marca()
    if abs(diferencia) < TOLERANCIA:
        return None
    desfase = equipo - time.time()
    return diferencia
