#!/usr/bin/env python3
"""Pacientes inventados para probar la pestana Registros. Ninguno es una persona real.

Pasan por las mismas reglas que la pagina (basedatos.guardar_paciente) y quedan
marcados con creado_por = "datos-de-prueba", asi se borran sin tocar los reales.

Uso:
  python3 datos_prueba.py           agrega 20 pacientes al azar
  python3 datos_prueba.py borrar    borra solo los pacientes de prueba
"""
import random
import sys
from contextlib import closing
from datetime import date, datetime, time, timedelta

import basedatos

AUTOR = "datos-de-prueba"  # lleva guiones: ningun usuario puede llamarse asi

NOMBRES = {
    "F": ["María José", "Ana Lucía", "Sofía", "Andrea", "Gabriela", "Daniela", "Valeria", "Mónica",
          "Karla", "Luisa Fernanda", "Rosa María", "Claudia", "Silvia", "Paola", "Ingrid", "Astrid"],
    "M": ["José Carlos", "Luis Fernando", "Juan Pablo", "Carlos Eduardo", "Diego", "Kevin", "Mario",
          "Óscar", "Javier", "Byron", "Erick", "Edgar", "Marvin", "Rodrigo", "Jorge Mario", "Walter"],
}
APELLIDOS = ["López", "García", "Pérez", "Hernández", "González", "Rodríguez", "Morales", "Méndez",
             "Castillo", "Ramírez", "Reyes", "Juárez", "Orellana", "Barrios", "Cifuentes", "Sandoval",
             "Pineda", "Recinos", "Ajú", "Xicará", "Cumes", "Monzón", "Estrada", "Velásquez", "Girón"]
FISIOTERAPEUTAS = ["Lcda. Andrea Morales", "Lic. José Pablo Cifuentes", "Lcda. Karla Recinos", "Lic. Diego Estrada"]
DOMINIOS = ["gmail.com", "gmail.com", "hotmail.com", "outlook.com", "yahoo.com"]
DEPARTAMENTOS = ["0101", "0101", "0108", "0115", "0301", "0501", "0901"]  # codigo de depto. y municipio del DPI

# Grupo: (cuantos, anos de nacimiento, diagnosticos, parentescos de emergencia, notas propias)
# "pareja" pasa a esposo o esposa segun el paciente
GRUPOS = [
    (8, (2000, 2006), [
        "Esguince de tobillo derecho grado II",
        "Postoperatorio de reconstrucción de LCA, rodilla derecha (semana 6)",
        "Síndrome patelofemoral bilateral",
        "Distensión de isquiotibiales grado I, pierna izquierda",
        "Cervicalgia por postura sostenida frente a la computadora",
        "Dorsalgia por escoliosis leve",
        "Tendinitis de De Quervain, muñeca derecha",
        "Fascitis plantar izquierda",
    ], ["madre", "padre", "hermana", "hermano"], [
        "Juega fútbol los fines de semana. Quiere volver a entrenar.",
        "Viene entre clases: prefiere citas por la mañana.",
    ]),
    (7, (1972, 1999), [
        "Lumbalgia mecánica crónica",
        "Hernia discal L5-S1 con radiculopatía izquierda",
        "Epicondilitis lateral derecha",
        "Síndrome del túnel carpiano derecho",
        "Tendinopatía del manguito rotador, hombro izquierdo",
        "Cefalea tensional con contractura de trapecios",
        "Fractura de radio distal izquierdo, posterior al retiro del yeso",
    ], ["pareja", "pareja", "hermana", "madre"], [
        "Trabaja 8 horas al día frente a la computadora.",
        "Solo puede asistir después de las 4:00 PM.",
    ]),
    (5, (1946, 1971), [
        "Gonartrosis bilateral grado II",
        "Capsulitis adhesiva de hombro derecho",
        "Hemiparesia derecha secundaria a ACV isquémico",
        "Bursitis trocantérica derecha",
        "Rehabilitación postoperatoria de prótesis total de cadera izquierda",
    ], ["hija", "hijo", "pareja"], [
        "Hipertensión controlada: tomar la presión antes de cada sesión.",
        "Diabetes tipo 2.",
        "Usa andador y llega con un familiar.",
    ]),
]
NOTAS_COMUNES = [
    "Refiere mejoría desde la última sesión.",
    "Trae resonancia magnética. Pendiente revisarla con el traumatólogo.",
    "Indicar ejercicios de fortalecimiento en casa.",
    "Llegó tarde a las dos últimas citas.",
]
TILDES = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")


def dpi(azar):
    """13 numeros: 8 al azar, el verificador (modulo 11) y el depto. y municipio."""
    while True:
        base = [azar.randint(0, 9) for _ in range(8)]
        verificador = sum(n * (i + 2) for i, n in enumerate(base)) % 11
        if verificador < 10:
            return "".join(map(str, base)) + str(verificador) + azar.choice(DEPARTAMENTOS)


def telefono(azar):
    return str(azar.choice([3, 4, 5])) + "".join(str(azar.randint(0, 9)) for _ in range(7))


def correo(azar, nombres, apellidos):
    usuario = f"{nombres.split()[0]}.{apellidos.split()[0]}{azar.randint(1, 99)}"
    return f"{usuario.lower().translate(TILDES)}@{azar.choice(DOMINIOS)}"


def emergencia(azar, apellidos, parentesco):
    """El apellido sigue la familia: padre y hermanos llevan el primero, la madre el segundo."""
    primero, segundo = apellidos.split()
    sexo = "M" if parentesco in ("padre", "hermano", "hijo", "esposo") else "F"
    apellido = {"madre": segundo, "esposa": azar.choice(APELLIDOS), "esposo": azar.choice(APELLIDOS)}.get(parentesco, primero)
    return f"{azar.choice(NOMBRES[sexo]).split()[0]} {apellido} ({parentesco})"


def medidas(azar, sexo):
    """Estatura (m) cercana al promedio de Guatemala y peso (lb) con un IMC de 19.5 a 31."""
    estatura = round(min(max(azar.gauss(1.53 if sexo == "F" else 1.65, 0.065), 1.40), 1.90), 2)
    kilos = azar.uniform(19.5, 31) * estatura ** 2
    return estatura, round(kilos * 2.20462, 1)


def cita(azar):
    """Dia habil de las proximas 3 semanas, de 7:00 a 17:30 cada media hora. A veces ninguna o una ya pasada."""
    suerte = azar.random()
    if suerte < 0.15:
        return None
    dia = date.today() + timedelta(days=azar.randint(-6, -1) if suerte < 0.25 else azar.randint(1, 21))
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    minutos = 7 * 60 + 30 * azar.randint(0, 21)
    return datetime.combine(dia, time(minutos // 60, minutos % 60)).strftime("%Y-%m-%d %H:%M")


def paciente(azar, anos, diagnosticos, parentescos, notas):
    sexo = azar.choice("FM")
    nombres = azar.choice(NOMBRES[sexo])
    apellidos = " ".join(azar.sample(APELLIDOS, 2))
    nacio = date(azar.randint(*anos), azar.randint(1, 12), azar.randint(1, 28))
    estudiante = anos[0] >= 2000
    estatura, peso = medidas(azar, sexo)
    parentesco = azar.choice(parentescos)
    if parentesco == "pareja":
        parentesco = "esposo" if sexo == "F" else "esposa"
    return {
        "nombres": nombres,
        "apellidos": apellidos,
        "sexo": sexo,
        "nacimiento": nacio.isoformat(),
        "dpi": dpi(azar),
        "carne": f"{azar.randint(2019, 2024)}{azar.randint(10000, 99999)}" if estudiante else None,
        "telefono": telefono(azar),
        "correo": correo(azar, nombres, apellidos) if azar.random() < 0.85 else None,
        "emergencia_nombre": emergencia(azar, apellidos, parentesco) if azar.random() < 0.9 else None,
        "emergencia_telefono": telefono(azar),
        "estatura": estatura,
        "peso": peso,
        "fisioterapeuta": azar.choice(FISIOTERAPEUTAS),
        "diagnostico": azar.choice(diagnosticos),
        "dolor": azar.choice([0, 2, 3, 3, 4, 5, 5, 6, 6, 7, 8]),
        "proxima_cita": cita(azar),
        "notas": azar.choice(NOTAS_COMUNES + notas) if azar.random() < 0.6 else None,
    }


def agregar():
    azar = random.Random()
    hechos = 0
    for cuantos, *grupo in GRUPOS:
        for _ in range(cuantos):
            datos = paciente(azar, *grupo)
            if not datos["emergencia_nombre"]:
                datos["emergencia_telefono"] = None
            _, error = basedatos.guardar_paciente(None, datos, AUTOR)
            if error:
                sys.exit(f"No se pudo guardar un paciente de prueba: {error[1]}")
            hechos += 1
    print(f"Listo: {hechos} pacientes de prueba. Para quitarlos:  python3 web/datos_prueba.py borrar")


def borrar():
    with closing(basedatos.abrir()) as con, con:
        borrados = con.execute("DELETE FROM pacientes WHERE creado_por = ?", (AUTOR,)).rowcount
    print(f"Listo: se borraron {borrados} pacientes de prueba. Los demás registros no se tocaron.")


if __name__ == "__main__":
    basedatos.iniciar()
    orden = sys.argv[1:]
    if not orden:
        agregar()
    elif orden == ["borrar"]:
        borrar()
    else:
        sys.exit(__doc__)
