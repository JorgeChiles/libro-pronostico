"""Rutas, caché y definición de las frecuencias de M4.

Tres decisiones que conviene tener a la vista:

1. **La caché vive fuera del repositorio.** Por defecto en
   `~/.cache/libro-pronostico/`. Se puede mover con la variable de entorno
   `LIBRO_CACHE`. Así el repositorio no engorda y OneDrive no sincroniza
   cientos de megabytes.

2. **El catálogo curado sí vive en el repositorio.** Son ~30 series y pesan
   poco. El libro entero compila con eso, sin conexión y sin caché.

3. **El período estacional es el de M4, no el "natural".** M4 declara Weekly
   y Daily como no estacionales (m=1) aunque lo natural sería 52 y 7. Usar
   otro valor rompe la comparabilidad con los resultados publicados de la
   competencia. Se exponen los dos: `periodo_estacional` (M4) y
   `periodo_natural`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Frecuencia:
    """Todo lo que M4 fija para una frecuencia."""

    nombre: str            # como se la nombra en el libro
    etiqueta_m4: str       # como se llaman los archivos de la competencia
    prefijo: str           # primera letra de los identificadores: Y1, Q10, M3007
    horizonte: int         # pasos a pronosticar, fijados por la competencia
    periodo_estacional: int  # el m de M4
    periodo_natural: int     # el m que sugiere el calendario
    frecuencia_pandas: str   # alias de frecuencia para el índice de fechas


FRECUENCIAS: dict[str, Frecuencia] = {
    "anual": Frecuencia("anual", "Yearly", "Y", 6, 1, 1, "YS"),
    "trimestral": Frecuencia("trimestral", "Quarterly", "Q", 8, 4, 4, "QS"),
    "mensual": Frecuencia("mensual", "Monthly", "M", 18, 12, 12, "MS"),
    "semanal": Frecuencia("semanal", "Weekly", "W", 13, 1, 52, "W-MON"),
    "diaria": Frecuencia("diaria", "Daily", "D", 14, 1, 7, "D"),
    "horaria": Frecuencia("horaria", "Hourly", "H", 48, 24, 24, "h"),
}

# Búsqueda por prefijo del identificador: "M3007" -> mensual.
POR_PREFIJO: dict[str, Frecuencia] = {f.prefijo: f for f in FRECUENCIAS.values()}

# Nombres alternativos que un lector puede escribir sin pensarlo.
ALIAS_FRECUENCIA: dict[str, str] = {
    "yearly": "anual",
    "annual": "anual",
    "año": "anual",
    "quarterly": "trimestral",
    "monthly": "mensual",
    "mes": "mensual",
    "weekly": "semanal",
    "daily": "diaria",
    "diario": "diaria",
    "hourly": "horaria",
    "horario": "horaria",
    "hora": "horaria",
}

NIVELES_DIFICULTAD = ("baja", "media_baja", "media_alta", "alta")

# El pipeline de la tesis etiqueta los cuartiles en inglés.
NIVEL_DESDE_TESIS = {
    "low": "baja",
    "mid_low": "media_baja",
    "mid_high": "media_alta",
    "high": "alta",
}


def normalizar_frecuencia(valor: str) -> Frecuencia:
    """Acepta 'mensual', 'Monthly', 'monthly' o 'M' y devuelve la Frecuencia."""
    clave = str(valor).strip().lower()
    clave = ALIAS_FRECUENCIA.get(clave, clave)
    if clave in FRECUENCIAS:
        return FRECUENCIAS[clave]
    prefijo = str(valor).strip().upper()
    if prefijo in POR_PREFIJO:
        return POR_PREFIJO[prefijo]
    validas = ", ".join(FRECUENCIAS)
    raise ValueError(f"Frecuencia desconocida: {valor!r}. Las válidas son: {validas}.")


def frecuencia_de_id(identificador: str) -> Frecuencia:
    """Deduce la frecuencia del identificador de M4: 'Q1120' -> trimestral."""
    ident = str(identificador).strip().upper()
    if not ident or ident[0] not in POR_PREFIJO:
        raise ValueError(
            f"Identificador de M4 no reconocido: {identificador!r}. "
            "Tienen la forma Y1, Q10, M3007, W20, D5, H100."
        )
    return POR_PREFIJO[ident[0]]


def directorio_paquete() -> Path:
    return Path(__file__).resolve().parent


def directorio_curado() -> Path:
    """Datos que viajan con el repositorio: el catálogo y los metadatos."""
    return directorio_paquete() / "curado"


def directorio_cache() -> Path:
    """Caché local, fuera del repositorio."""
    if ruta := os.environ.get("LIBRO_CACHE"):
        destino = Path(ruta).expanduser()
    else:
        destino = Path.home() / ".cache" / "libro-pronostico"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def origenes_posibles() -> list[Path]:
    """Dónde buscar los CSV originales de M4, en orden de preferencia."""
    candidatos: list[Path] = []
    if ruta := os.environ.get("LIBRO_M4_ORIGEN"):
        candidatos.append(Path(ruta).expanduser())
    candidatos.append(directorio_cache() / "m4_csv")
    # Copia local del proyecto de la tesis, si está a mano.
    tesis = Path.home() / (
        "Library/CloudStorage/OneDrive-Personal/MAESTRIA2025/TESIS/"
        "m4-structural-complexity/data"
    )
    candidatos.append(tesis)
    return candidatos


# Espejo oficial de los datos de M4 (repositorio de la competencia).
URL_M4 = (
    "https://raw.githubusercontent.com/Mcompetitions/M4-methods/master/Dataset/"
)
