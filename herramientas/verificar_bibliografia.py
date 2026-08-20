"""Comprueba `referencias.bib` contra Crossref.

Se usa cuando se agregan entradas nuevas:

    python herramientas/verificar_bibliografia.py

Hace dos cosas distintas y ninguna necesita compilar el libro:

1. **Valida los DOI que ya están.** Resuelve cada uno contra Crossref y
   compara el título que devuelve con el de la entrada. Un DOI que no resuelve,
   o que resuelve a otro trabajo, es un error que nadie ve leyendo el libro.
2. **Busca por título las entradas sin DOI** y reporta si el año, el volumen,
   las páginas o la revista no coinciden con lo que Crossref tiene registrado.

Lo que **no** puede: libros anteriores al DOI, JMLR, y las actas de NeurIPS,
MLSys, ICLR y SciPy, que Crossref no indexa o indexa con títulos abreviados.
Esas hay que verificarlas en el sitio del editor; están anotadas en `SIN_CROSSREF`
para que el reporte no las marque cada vez.

Requiere red. No corre en `make prueba` por eso mismo.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

BIB = Path(__file__).resolve().parent.parent / "referencias.bib"
UA = "libro-pronostico/1.0 (verificacion de bibliografia)"

# Verificadas a mano en el sitio del editor, no en Crossref.
# Crossref registra el título recortado, así que la comparación da un ratio bajo
# aunque el DOI sea el correcto. Verificadas a mano.
TITULO_ABREVIADO_EN_CROSSREF = {
    "chen2016",    # registrado como «XGBoost», sin el subtítulo
    "hastie2009",  # registrado sin el subtítulo del libro
}

SIN_CROSSREF = {
    "boxjenkins1970", "tukey1977", "cleveland1993", "cleveland1990",
    "demsar2006", "demsar2008", "pedregosa2011", "cawley2010",
    "godahewa2021", "grinsztajn2022", "ke2017", "sculley2015",
    "bouthillier2021", "oreshkin2020", "hyndman2021",
    # Crossref solo tiene la reimpresión de 2017 en CACM; la cita correcta es la
    # original de NIPS 2012, que no tiene DOI.
    "krizhevsky2012", "vaswani2017",
}


def limpio(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", re.sub(r"[{}\\]", "", s or "").lower()).strip()


def entradas():
    texto = BIB.read_text()
    for m in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", texto, re.S):
        campos = {}
        for f in re.finditer(r"(\w+)\s*=\s*[{\"](.*?)[}\"],?\s*\n", m.group(3) + "\n", re.S):
            campos[f.group(1).lower()] = re.sub(r"\s+", " ", f.group(2)).strip()
        yield {"tipo": m.group(1), "clave": m.group(2).strip(), **campos}


def pedir(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def por_doi(doi: str):
    return pedir(f"https://api.crossref.org/works/{doi}")["message"]


def por_titulo(titulo: str, autor: str):
    q = urllib.parse.urlencode({
        "query.bibliographic": f"{titulo} {autor}", "rows": "3",
        "select": "title,container-title,volume,issue,page,issued,DOI",
    })
    return pedir(f"https://api.crossref.org/works?{q}")["message"]["items"]


def comparar(entrada, obra) -> list[str]:
    dif = []
    anio = str(obra["issued"]["date-parts"][0][0])
    if entrada.get("year") and entrada["year"] != anio:
        dif.append(f"año {entrada['year']}→{anio}")
    for campo, en_crossref in [("volume", "volume"), ("pages", "page")]:
        nuestro = (entrada.get(campo) or "").replace("--", "-")
        suyo = str(obra.get(en_crossref) or "")
        if nuestro and suyo and nuestro != suyo and not suyo.startswith(nuestro.split("-")[0]):
            dif.append(f"{campo} {nuestro}→{suyo}")
    return dif


def main() -> int:
    problemas = 0
    for e in entradas():
        clave, titulo = e["clave"], e.get("title", "")
        if e.get("doi"):
            try:
                obra = por_doi(e["doi"])
            except Exception:
                print(f"DOI NO RESUELVE  {clave}: {e['doi']}")
                problemas += 1
                continue
            r = SequenceMatcher(None, limpio(titulo), limpio((obra.get("title") or [""])[0])).ratio()
            # Crossref registra algunos títulos abreviados («XGBoost», libros sin subtítulo).
            if r < 0.55 and clave not in TITULO_ABREVIADO_EN_CROSSREF:
                print(f"DOI DE OTRA OBRA {clave}: {e['doi']} → «{(obra.get('title') or [''])[0][:60]}»")
                problemas += 1
                continue
            for d in comparar(e, obra):
                print(f"DIFIERE          {clave}: {d}")
                problemas += 1
        elif clave not in SIN_CROSSREF:
            try:
                items = por_titulo(limpio(titulo), limpio((e.get("author") or "").split(" and ")[0]))
            except Exception as exc:
                print(f"ERROR DE RED     {clave}: {exc}")
                continue
            mejor, ratio = None, 0.0
            for it in items:
                r = SequenceMatcher(None, limpio(titulo), limpio((it.get("title") or [""])[0])).ratio()
                if r > ratio:
                    mejor, ratio = it, r
            if mejor and ratio > 0.9:
                print(f"SIN DOI          {clave}: Crossref la tiene, {mejor['DOI']}")
                problemas += 1
        time.sleep(0.3)
    print(f"\n{'sin problemas' if not problemas else f'{problemas} cosas para revisar'}")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
