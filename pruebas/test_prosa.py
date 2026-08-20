"""Pruebas de la prosa del libro, no de su código.

Quarto resuelve `@sec-x` como «Capítulo N» si `x` etiqueta un encabezado de
nivel 1 y como «Sección N.M» si es de nivel 2 o más. El artículo lo escribe
quien redacta, así que «el @sec-costo» sale publicado como «el Sección 23.7».

Es un error que no rompe la compilación, no aparece en ningún registro y se
multiplica solo: había 216 en el libro cuando se escribió esta prueba. De ahí
que valga una prueba y no una revisión.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

FUENTES = sorted(
    [*(RAIZ / "capitulos").glob("*.qmd"),
     *(RAIZ / "apendices").glob("*.qmd"),
     RAIZ / "index.qmd",
     RAIZ / "laboratorio" / "interactividad.qmd"]
)

MASCULINO = re.compile(r"(—?(?:el|El|del|Del|al|Al))(\s+)@(sec-[a-z0-9-]+)")
FEMENINO = re.compile(r"\b(la|La|de la|De la|a la)(\s+)@(sec-[a-z0-9-]+)")
ENCABEZADO = re.compile(r"^(#+)\s+.*\{#(sec-[a-z0-9-]+)\}")


def _nivel_de_cada_seccion() -> dict[str, int]:
    """Qué nivel de encabezado tiene cada identificador `sec-` del libro."""
    niveles = {}
    for ruta in FUENTES:
        for linea in ruta.read_text().splitlines():
            m = ENCABEZADO.match(linea)
            if m:
                niveles[m.group(2)] = len(m.group(1))
    return niveles


def _sin_bloques_de_codigo(texto: str) -> str:
    return re.sub(r"```.*?```", "", texto, flags=re.S)


def test_el_articulo_concuerda_con_capitulo_o_seccion():
    niveles = _nivel_de_cada_seccion()
    fallas = []
    for ruta in FUENTES:
        texto = _sin_bloques_de_codigo(ruta.read_text())
        for m in MASCULINO.finditer(texto):
            if niveles.get(m.group(3), 1) > 1:
                fallas.append(f"{ruta.name}: «{m.group(0)}» → «Sección», va en femenino")
        for m in FEMENINO.finditer(texto):
            if niveles.get(m.group(3), 9) == 1:
                fallas.append(f"{ruta.name}: «{m.group(0)}» → «Capítulo», va en masculino")
    assert not fallas, "concordancia de género en referencias:\n  " + "\n  ".join(fallas)


def test_todas_las_referencias_apuntan_a_algo_que_existe():
    """La red de seguridad de `make referencias`, sin compilar el libro."""
    definidos = set(_nivel_de_cada_seccion())
    for ruta in FUENTES:
        for linea in ruta.read_text().splitlines():
            m = re.match(r"^(#+)\s+.*\{#((?:tbl|fig|eq)-[a-z0-9-]+)\}", linea)
            if m:
                definidos.add(m.group(2))
            for etiqueta in re.findall(r"^#\|\s*label:\s*([a-z0-9-]+)\s*$", linea):
                definidos.add(etiqueta)
            for etiqueta in re.findall(r"\{#((?:tbl|fig|eq)-[a-z0-9-]+)\}", linea):
                definidos.add(etiqueta)

    faltantes = []
    for ruta in FUENTES:
        texto = _sin_bloques_de_codigo(ruta.read_text())
        for ref in re.findall(r"@((?:sec|tbl|fig|eq)-[a-z0-9-]+)", texto):
            if ref not in definidos:
                faltantes.append(f"{ruta.name}: @{ref}")
    assert not faltantes, "referencias sin destino:\n  " + "\n  ".join(sorted(set(faltantes)))


def test_los_decimales_en_linea_llevan_coma():
    """El libro escribe 0,7 y no 0.7, también cuando el número lo calcula Python.

    Una expresión en línea como `{python} f"{x:.1f}"` publica un punto decimal
    en medio de una prosa que usa coma. Es invisible al escribir y salta a la
    vista en la página: pasó con «daña a lo sumo 0.7 puntos» del capítulo 25,
    que se vio recién en el sitio publicado.
    """
    formato = re.compile(r"`\{python\}[^`]*`")
    decimal = re.compile(r":,?\.[1-9]f\}")
    fallas = []
    for ruta in FUENTES:
        for numero, linea in enumerate(ruta.read_text().split("\n"), 1):
            for m in formato.finditer(linea):
                expresion = m.group(0)
                if not decimal.search(expresion):
                    continue
                if 'replace(".", ",")' in expresion or 'replace(".", "{,}")' in expresion:
                    continue
                fallas.append(f"{ruta.name}:{numero}: {expresion[:80]}")
    assert not fallas, "decimales con punto en la prosa:\n  " + "\n  ".join(fallas)


def test_el_libro_usa_tuteo_y_no_voseo():
    """La regla editorial: español latinoamericano con tuteo."""
    voseo = re.compile(
        r"\b(tenés|podés|querés|sabés|hacés|mirá|fijate|acordate|dale|"
        r"volvé|agregá|calculá|compará|clasificá|repetí|repetila|barrelo|"
        r"probá|elegí|usá|medí|corré|escribí)\b"
    )
    fallas = []
    for ruta in FUENTES:
        texto = _sin_bloques_de_codigo(ruta.read_text())
        for m in voseo.finditer(texto):
            fallas.append(f"{ruta.name}: «{m.group(0)}»")
    assert not fallas, "voseo donde va tuteo:\n  " + "\n  ".join(fallas)
