"""Construye los metadatos y el catálogo curado de series del libro.

Dos salidas, las dos van al repositorio porque pesan poco y son lo que hace que
el libro compile sin conexión:

1. `metadatos.parquet` — una fila por cada una de las 100.000 series de M4:
   frecuencia, horizonte, período estacional, categoría económica, largo, el
   índice de complejidad estructural con su cuartil, el clúster, las tres
   entropías clásicas y el error del naive. Pesa pocos megabytes.

2. `catalogo.parquet` — las ~30 series curadas, con sus valores completos
   (entrenamiento y prueba) y la etiqueta del fenómeno que ilustra cada una.

**Cómo se eligen las 30.** No a dedo. Se parte de los 29 descriptores
estructurales calculados sobre las 100.000 series y del índice de complejidad
(PC1 invertido del PCA sobre esos descriptores). Para cada fenómeno se define
un criterio explícito sobre los descriptores, se ordena por qué tan
inequívocamente la serie ilustra ese fenómeno, y se toma la mejor que además no
esté ya elegida. Al final se completa para que los cuatro cuartiles de
dificultad queden representados.

Entrada: los resultados del pipeline de la tesis (m4-structural-complexity).
Se corre una vez:

    python -m libro._construir_catalogo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from libro.datos.rutas import (
    FRECUENCIAS,
    NIVEL_DESDE_TESIS,
    directorio_cache,
    directorio_curado,
    frecuencia_de_id,
)

RUTA_TESIS = Path.home() / (
    "Library/CloudStorage/OneDrive-Personal/MAESTRIA2025/TESIS"
)

# Columnas de los descriptores que el libro conserva. Son las que se usan para
# curar el catálogo y las que el capítulo 5 necesita para hablar de
# características de series.
DESCRIPTORES = [
    "trend_strength",
    "seasonal_strength",
    "z_trend_linearity_r2",
    "z_hurst",
    "z_acf1",
    "z_entropy",
    "z_spectral_entropy",
    "z_outlier_ratio",
    "z_turning_points_ratio",
    "adf_pvalue",
    "kpss_pvalue",
    "diff_var_ratio",
    "change_points_per_length",
    "dominant_energy_ratio",
]

# Un fenómeno por fila: nombre, descripción para el lector, y el criterio.
# `puntaje` recibe el DataFrame de metadatos y devuelve una serie: más alto,
# mejor ejemplo del fenómeno. `filtro` es la condición dura que hay que cumplir.
FENOMENOS: list[dict] = [
    {
        "nombre": "tendencia-limpia",
        "descripcion": "Tendencia fuerte y casi lineal, con poco ruido alrededor",
        "filtro": lambda d: (d["trend_strength"] > 0.9) & (d["seasonal_strength"] < 0.3),
        "puntaje": lambda d: d["trend_strength"] + d["z_trend_linearity_r2"].clip(-3, 3) / 3,
        "cupo": 3,
    },
    {
        "nombre": "estacionalidad-marcada",
        "descripcion": "Ciclo estacional dominante y estable",
        "filtro": lambda d: (d["seasonal_strength"] > 0.85) & (d["periodo_estacional"] > 1),
        "puntaje": lambda d: d["seasonal_strength"] + d["dominant_energy_ratio"].fillna(0),
        "cupo": 4,
    },
    {
        "nombre": "tendencia-y-estacionalidad",
        "descripcion": "Las dos componentes fuertes a la vez: el caso de Holt-Winters",
        "filtro": lambda d: (d["trend_strength"] > 0.8) & (d["seasonal_strength"] > 0.7),
        "puntaje": lambda d: d["trend_strength"] * d["seasonal_strength"],
        "cupo": 3,
    },
    {
        "nombre": "caminata-aleatoria",
        "descripcion": "Sin estructura explotable: el naive es difícil de superar",
        "filtro": lambda d: (
            (d["trend_strength"] < 0.4)
            & (d["seasonal_strength"] < 0.3)
            & (d["adf_pvalue"] > 0.5)
        ),
        "puntaje": lambda d: d["complexity_index"],
        "cupo": 4,
    },
    {
        "nombre": "quiebre-de-nivel",
        "descripcion": "La serie cambia de nivel de golpe y no vuelve",
        "filtro": lambda d: d["change_points_per_length"].notna(),
        "puntaje": lambda d: d["change_points_per_length"],
        "cupo": 3,
    },
    {
        "nombre": "cambio-de-varianza",
        "descripcion": "La amplitud de las fluctuaciones crece o se reduce con el nivel",
        "filtro": lambda d: d["diff_var_ratio"].notna() & (d["n_entrenamiento"] > 40),
        "puntaje": lambda d: d["diff_var_ratio"],
        "cupo": 3,
    },
    {
        "nombre": "atipicos",
        "descripcion": "Observaciones extremas aisladas que distorsionan el ajuste",
        "filtro": lambda d: d["z_outlier_ratio"].notna(),
        "puntaje": lambda d: d["z_outlier_ratio"],
        "cupo": 2,
    },
    {
        "nombre": "serie-corta",
        "descripcion": "Tan pocas observaciones que casi no hay con qué estimar",
        "filtro": lambda d: d["n_entrenamiento"] <= 20,
        "puntaje": lambda d: -d["n_entrenamiento"],
        "cupo": 3,
    },
    {
        "nombre": "serie-larga",
        "descripcion": "Miles de observaciones: alcanza para modelos con muchos parámetros",
        "filtro": lambda d: d["n_entrenamiento"] > 1000,
        "puntaje": lambda d: d["n_entrenamiento"],
        "cupo": 3,
    },
    {
        "nombre": "estacionalidad-multiple",
        "descripcion": "Ciclo diario y semanal a la vez, en datos horarios",
        "filtro": lambda d: (d["frecuencia"] == "horaria") & (d["n_entrenamiento"] > 700),
        "puntaje": lambda d: d["seasonal_strength"],
        "cupo": 2,
    },
]


def _leer(ruta: Path, columnas: list[str] | None = None) -> pd.DataFrame:
    """Lee un xlsx del pipeline de la tesis, con caché en parquet."""
    cache = directorio_cache() / "tesis" / (ruta.stem + ".parquet")
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        df = pd.read_parquet(cache)
    else:
        print(f"  leyendo {ruta.name} (primera vez, tarda) ...", flush=True)
        df = pd.read_excel(ruta)
        df.to_parquet(cache, index=False)
    return df[columnas] if columnas else df


def construir_metadatos() -> pd.DataFrame:
    res = RUTA_TESIS / "m4-structural-complexity" / "results"

    cols = ["serie", "category", "freq", "horizon", "n_valid", "complexity_index",
            "complexity_level", "cluster"] + DESCRIPTORES
    clustered = _leer(res / "df_features_clustered.xlsx")
    faltan = [c for c in cols if c not in clustered.columns]
    if faltan:
        sys.exit(f"Faltan columnas en df_features_clustered.xlsx: {faltan}")
    meta = clustered[cols].copy()

    entropia = _leer(res / "df_entropy.xlsx",
                     ["serie", "perm_entropy", "sample_entropy", "lz_complexity"])
    meta = meta.merge(entropia, on="serie", how="left")

    errores = _leer(res / "forecasting_errors_completo.xlsx",
                    ["serie", "error_naive_smape", "error_snaive_smape",
                     "error_arima_smape"])
    meta = meta.merge(errores, on="serie", how="left")

    # Metadatos oficiales de la competencia. La categoría económica sale de
    # acá: la columna `category` del pipeline de la tesis guarda la frecuencia,
    # no la categoría (Macro, Micro, Finance, Industry, Demographic, Other).
    info = pd.read_csv(RUTA_TESIS / "TRANSPOSE_1000_RANDOM" / "m4_info.csv")
    info = info.rename(columns={"M4id": "serie", "SP": "etiqueta_m4",
                                "StartingDate": "fecha_inicio",
                                "category": "categoria_m4"})
    meta = meta.merge(info[["serie", "categoria_m4", "etiqueta_m4", "fecha_inicio"]],
                      on="serie", how="left")
    meta["category"] = meta["categoria_m4"]
    meta = meta.drop(columns=["categoria_m4"])
    # M4 declara la fecha de inicio con hora 12:00; el libro usa el día.
    meta["fecha_inicio"] = (
        pd.to_datetime(meta["fecha_inicio"], dayfirst=True, errors="coerce")
        .dt.normalize()
    )

    # Nombres del libro, en español, y las convenciones de M4.
    meta["frecuencia"] = [frecuencia_de_id(s).nombre for s in meta["serie"]]
    meta["periodo_estacional"] = meta["frecuencia"].map(
        {n: f.periodo_estacional for n, f in FRECUENCIAS.items()})
    meta["periodo_natural"] = meta["frecuencia"].map(
        {n: f.periodo_natural for n, f in FRECUENCIAS.items()})
    meta["horizonte"] = meta["frecuencia"].map(
        {n: f.horizonte for n, f in FRECUENCIAS.items()})
    meta["dificultad"] = meta["complexity_level"].astype(str).map(NIVEL_DESDE_TESIS)

    meta = meta.rename(columns={"category": "categoria", "n_valid": "n_entrenamiento"})
    meta = meta.drop(columns=["freq", "horizon", "complexity_level"])

    # Los descriptores se guardan en float32: la precisión de float64 no aporta
    # nada acá y el archivo, que viaja en el repositorio, pesa la mitad.
    flotantes = meta.select_dtypes("float64").columns
    meta[flotantes] = meta[flotantes].astype("float32")
    for col in ("categoria", "frecuencia", "dificultad", "etiqueta_m4"):
        if col in meta.columns:
            meta[col] = meta[col].astype("category")
    return meta


# Cuántas series como mínimo por cuartil de dificultad. Sin esto el catálogo se
# escora a las difíciles: casi todos los fenómenos interesantes correlacionan
# con complejidad alta.
MINIMO_POR_DIFICULTAD = 5


def curar(meta: pd.DataFrame) -> pd.DataFrame:
    """Elige las series del catálogo aplicando los criterios de FENOMENOS."""
    elegidas: list[dict] = []
    usadas: set[str] = set()

    def anotar(fila, fenomeno: str, descripcion: str) -> None:
        elegidas.append({"serie": fila["serie"], "fenomeno": fenomeno,
                         "descripcion_fenomeno": descripcion})
        usadas.add(fila["serie"])

    for fen in FENOMENOS:
        candidatas = meta[fen["filtro"](meta)].copy()
        if candidatas.empty:
            print(f"  aviso: sin candidatas para {fen['nombre']}")
            continue
        candidatas["_puntaje"] = fen["puntaje"](candidatas)
        candidatas = candidatas.sort_values("_puntaje", ascending=False)

        # Dos pasadas. La primera reparte entre frecuencias para que el
        # catálogo no quede concentrado en una sola; la segunda llena los cupos
        # que hayan quedado vacíos sin esa restricción.
        tomadas = 0
        frecuencias_vistas: set[str] = set()
        for exigir_variedad in (True, False):
            for _, fila in candidatas.iterrows():
                if tomadas >= fen["cupo"]:
                    break
                if fila["serie"] in usadas:
                    continue
                if exigir_variedad and fila["frecuencia"] in frecuencias_vistas:
                    continue
                anotar(fila, fen["nombre"], fen["descripcion"])
                frecuencias_vistas.add(fila["frecuencia"])
                tomadas += 1
            if tomadas >= fen["cupo"]:
                break
        if tomadas < fen["cupo"]:
            print(f"  aviso: {fen['nombre']} quedó con {tomadas} de {fen['cupo']}")

    # Cobertura del espectro de dificultad. Se toma la serie más "típica" de
    # cada cuartil que falte: la de complejidad más cercana a la mediana del
    # cuartil, para que sea representativa y no un caso de borde.
    ya = pd.DataFrame(elegidas).merge(meta[["serie", "dificultad"]], on="serie")
    for nivel in NIVEL_DESDE_TESIS.values():
        faltan = MINIMO_POR_DIFICULTAD - int((ya["dificultad"] == nivel).sum())
        if faltan <= 0:
            continue
        pozo = meta[(meta["dificultad"] == nivel) & (~meta["serie"].isin(usadas))].copy()
        if pozo.empty:
            continue
        centro = pozo["complexity_index"].median()
        pozo["_dist"] = (pozo["complexity_index"] - centro).abs()
        # Se reparte entre frecuencias también acá.
        pozo = pozo.sort_values("_dist")
        vistas: set[str] = set()
        puestas = 0
        for exigir_variedad in (True, False):
            for _, fila in pozo.iterrows():
                if puestas >= faltan:
                    break
                if fila["serie"] in usadas:
                    continue
                if exigir_variedad and fila["frecuencia"] in vistas:
                    continue
                anotar(fila, "cobertura-de-dificultad",
                       f"Serie representativa del cuartil de dificultad {nivel}")
                vistas.add(fila["frecuencia"])
                puestas += 1
            if puestas >= faltan:
                break

    catalogo = pd.DataFrame(elegidas).merge(meta, on="serie", how="left")
    return catalogo.sort_values(["fenomeno", "serie"]).reset_index(drop=True)


def valores_de(series_ids: list[str]) -> pd.DataFrame:
    """Trae las observaciones de las series elegidas desde la caché en parquet."""
    partes = []
    por_frecuencia: dict[str, list[str]] = {}
    for sid in series_ids:
        por_frecuencia.setdefault(frecuencia_de_id(sid).nombre, []).append(sid)

    for frecuencia, ids in por_frecuencia.items():
        archivo = directorio_cache() / "m4" / f"{frecuencia}.parquet"
        if not archivo.exists():
            sys.exit(
                f"Falta la caché {archivo}. Corré primero:\n"
                "  python -m libro._construir_cache"
            )
        df = pd.read_parquet(archivo)
        partes.append(df[df["serie"].astype(str).isin(ids)])
    return pd.concat(partes, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destino", default=None)
    args = parser.parse_args()
    destino = Path(args.destino).expanduser() if args.destino else directorio_curado()
    destino.mkdir(parents=True, exist_ok=True)

    print("Metadatos de las 100.000 series ...")
    meta = construir_metadatos()
    print(f"  {len(meta):,} series · {len(meta.columns)} columnas")

    ruta_meta = destino / "metadatos.parquet"
    meta.to_parquet(ruta_meta, index=False, compression="zstd")
    print(f"  -> {ruta_meta.name} ({ruta_meta.stat().st_size/1e6:.1f} MB)")

    print("\nCurando el catálogo ...")
    catalogo = curar(meta)
    print(f"  {len(catalogo)} series elegidas")
    print(catalogo.groupby("fenomeno").size().to_string())
    print("\n  por dificultad:")
    print(catalogo.groupby("dificultad").size().to_string())
    print("\n  por frecuencia:")
    print(catalogo.groupby("frecuencia").size().to_string())

    ruta_cat = destino / "catalogo.parquet"
    catalogo.to_parquet(ruta_cat, index=False, compression="zstd")

    print("\nValores de las series del catálogo ...")
    valores = valores_de(catalogo["serie"].astype(str).tolist())
    ruta_val = destino / "catalogo_valores.parquet"
    valores.to_parquet(ruta_val, index=False, compression="zstd")
    print(f"  {len(valores):,} observaciones -> {ruta_val.name} "
          f"({ruta_val.stat().st_size/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
