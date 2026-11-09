"""Archivos de la pagina: compone el HTML desde plantillas/ y entrega publico/.

Las dos carpetas se leen en cada visita: al editarlas basta con recargar la pagina.
"""
import re
from pathlib import Path

CARPETA = Path(__file__).parent
PLANTILLAS = CARPETA / "plantillas"
PUBLICO = (CARPETA / "publico").resolve()

# Solo se entregan estos tipos, y solo desde publico/: camilla.db y el codigo Python quedan fuera
TIPOS = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",  # los modulos ES no cargan con otro tipo
    ".woff2": "font/woff2",
}
TIPO_HTML = "text/html; charset=utf-8"
INCLUIR = re.compile(r"<!--\s*incluir:\s*([\w./-]+)\s*-->")


def componer(nombre="index.html"):
    """Devuelve la plantilla con sus `<!-- incluir: ruta -->` ya resueltos (rutas desde plantillas/)."""
    html = (PLANTILLAS / nombre).read_text(encoding="utf-8")
    return INCLUIR.sub(lambda parcial: componer(parcial[1]), html)


def pagina():
    return componer().encode("utf-8"), TIPO_HTML


def archivo_publico(ruta):
    """Devuelve (contenido, tipo) del archivo de publico/ que pide la URL, o None si no se entrega."""
    try:
        archivo = (PUBLICO / ruta.lstrip("/")).resolve()
        if archivo.suffix in TIPOS and PUBLICO in archivo.parents and archivo.is_file():
            return archivo.read_bytes(), TIPOS[archivo.suffix]
    except (OSError, ValueError):  # ruta imposible, por ejemplo con un byte nulo
        pass
    return None
