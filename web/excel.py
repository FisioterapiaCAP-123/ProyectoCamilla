"""Registros de pacientes a un archivo de Excel (.xlsx), solo con la biblioteca estandar.

Un .xlsx es un ZIP con unos XML adentro: aqui se escriben los minimos que Excel,
LibreOffice y Google Sheets abren sin quejarse. Asi la Raspberry no necesita
instalar nada (la red Camilla no tiene internet).

DPI y telefonos van como texto: Excel los volveria numeros (2.35E+12, sin ceros).
Las fechas van como fechas de verdad, para poder ordenar y filtrar.
"""
import io
import re
import zipfile
from datetime import date, datetime
from xml.sax.saxutils import escape

TIPO = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SEXOS = {"F": "Femenino", "M": "Masculino"}
DIA_CERO = datetime(1899, 12, 30)  # Excel cuenta los dias desde aqui
NO_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")  # caracteres que XML no admite

# Estilos (indice en cellXfs de styles.xml)
ENCABEZADO, TEXTO, PARRAFO, FECHA, FECHA_HORA, DOS_DECIMALES, UN_DECIMAL, ENTERO = range(1, 9)


def agrupar(numero, grupos):
    """'2345678900101' -> '2345 67890 0101' (igual que en la pagina)."""
    partes, inicio = [], 0
    for largo in grupos:
        partes.append(numero[inicio:inicio + largo])
        inicio += largo
    return " ".join(p for p in partes if p)


def edad(nacimiento, hoy):
    if not nacimiento:
        return None
    nacio = date.fromisoformat(nacimiento)
    return hoy.year - nacio.year - ((hoy.month, hoy.day) < (nacio.month, nacio.day))


def fecha(texto, formato):
    try:
        return datetime.strptime(texto, formato) if texto else None
    except ValueError:
        return None


# (titulo, ancho, estilo, como sacar el dato del paciente)
COLUMNAS = [
    ("Apellidos", 22, TEXTO, lambda p, hoy: p["apellidos"]),
    ("Nombres", 22, TEXTO, lambda p, hoy: p["nombres"]),
    ("Sexo", 11, TEXTO, lambda p, hoy: SEXOS.get(p["sexo"])),
    ("Nacimiento", 12, FECHA, lambda p, hoy: fecha(p["nacimiento"], "%Y-%m-%d")),
    ("Edad", 7, ENTERO, lambda p, hoy: edad(p["nacimiento"], hoy)),
    ("DPI", 17, TEXTO, lambda p, hoy: p["dpi"] and agrupar(p["dpi"], (4, 5, 4))),
    ("Carné", 12, TEXTO, lambda p, hoy: p["carne"]),
    ("Teléfono", 11, TEXTO, lambda p, hoy: p["telefono"] and agrupar(p["telefono"], (4, 4))),
    ("Correo", 26, TEXTO, lambda p, hoy: p["correo"]),
    ("Contacto de emergencia", 24, TEXTO, lambda p, hoy: p["emergencia_nombre"]),
    ("Teléfono de emergencia", 13, TEXTO,
     lambda p, hoy: p["emergencia_telefono"] and agrupar(p["emergencia_telefono"], (4, 4))),
    ("Estatura (m)", 10, DOS_DECIMALES, lambda p, hoy: p["estatura"]),
    ("Peso (lb)", 9, UN_DECIMAL, lambda p, hoy: p["peso"]),
    ("Fisioterapeuta", 22, TEXTO, lambda p, hoy: p["fisioterapeuta"]),
    ("Dolor (0-10)", 9, ENTERO, lambda p, hoy: p["dolor"]),
    ("Diagnóstico", 40, PARRAFO, lambda p, hoy: p["diagnostico"]),
    ("Próxima cita", 22, FECHA_HORA, lambda p, hoy: fecha(p["proxima_cita"], "%Y-%m-%d %H:%M")),
    ("Notas", 40, PARRAFO, lambda p, hoy: p["notas"]),
    ("Registrado", 22, FECHA_HORA, lambda p, hoy: fecha(p["creado"], "%Y-%m-%d %H:%M")),
    ("Registrado por", 15, TEXTO, lambda p, hoy: p["creado_por"]),
]


def letra(indice):
    """0 -> A, 25 -> Z, 26 -> AA."""
    texto = ""
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        texto = chr(65 + resto) + texto
    return texto


def celda(ref, valor, estilo):
    if valor is None or valor == "":
        return ""
    if isinstance(valor, datetime):
        diferencia = valor - DIA_CERO
        dias = diferencia.days + diferencia.seconds / 86400
        return f'<c r="{ref}" s="{estilo}"><v>{dias!r}</v></c>'
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f'<c r="{ref}" s="{estilo}"><v>{valor}</v></c>'
    texto = escape(NO_XML.sub("", str(valor)))
    return f'<c r="{ref}" s="{estilo}" t="inlineStr"><is><t xml:space="preserve">{texto}</t></is></c>'


def hoja(pacientes, hoy):
    ultima = letra(len(COLUMNAS) - 1)
    filas = ['<row r="1">' + "".join(celda(f"{letra(i)}1", titulo, ENCABEZADO)
                                     for i, (titulo, *_) in enumerate(COLUMNAS)) + "</row>"]
    for n, p in enumerate(pacientes, start=2):
        filas.append(f'<row r="{n}">' + "".join(celda(f"{letra(i)}{n}", sacar(p, hoy), estilo)
                                               for i, (_, _, estilo, sacar) in enumerate(COLUMNAS)) + "</row>")
    anchos = "".join(f'<col min="{i}" max="{i}" width="{ancho}" customWidth="1"/>'
                     for i, (_, ancho, *_) in enumerate(COLUMNAS, start=1))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0">'  # el encabezado queda fijo al bajar
            '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
            '</sheetView></sheetViews>'
            f'<cols>{anchos}</cols>'
            f'<sheetData>{"".join(filas)}</sheetData>'
            f'<autoFilter ref="A1:{ultima}{max(len(pacientes) + 1, 2)}"/>'
            '</worksheet>')


ESTILOS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="3">
<numFmt numFmtId="164" formatCode="dd/mm/yyyy"/>
<numFmt numFmtId="165" formatCode="dd/mm/yyyy h:mm AM/PM"/>
<numFmt numFmtId="166" formatCode="0.0"/>
</numFmts>
<fonts count="2">
<font><sz val="11"/><name val="Calibri"/><family val="2"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/><family val="2"/></font>
</fonts>
<fills count="3">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E79"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="9">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment horizontal="left" vertical="top"/></xf>
<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment horizontal="left" vertical="top"/></xf>
<xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="1" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

TIPOS_CONTENIDO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

RELACIONES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

LIBRO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Registros" sheetId="1" r:id="rId1"/></sheets>
<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">Registros!$A$1:${ultima}${fin}</definedName></definedNames>
</workbook>"""

RELACIONES_LIBRO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def crear(pacientes, hoy=None):
    """Bytes del .xlsx con una fila por paciente, en el orden recibido."""
    hoy = hoy or date.today()
    ultima, fin = letra(len(COLUMNAS) - 1), max(len(pacientes) + 1, 2)
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", TIPOS_CONTENIDO)
        z.writestr("_rels/.rels", RELACIONES)
        z.writestr("xl/workbook.xml", LIBRO.replace("{ultima}", ultima).replace("{fin}", str(fin)))
        z.writestr("xl/_rels/workbook.xml.rels", RELACIONES_LIBRO)
        z.writestr("xl/styles.xml", ESTILOS)
        z.writestr("xl/worksheets/sheet1.xml", hoja(pacientes, hoy))
    return memoria.getvalue()
