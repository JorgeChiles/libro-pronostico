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

# Series que el texto nombra explícitamente y que por lo tanto tienen que viajar
# en el repositorio, elija lo que elija el algoritmo de curación. Si un capítulo
# usa una serie por identificador y no está acá, el libro intenta bajarla al
# compilar y deja de compilar sin conexión. Hay una prueba que lo verifica.
# Cada entrada es `identificador: (etiqueta, motivo)`. La etiqueta es el fenómeno
# que la serie ilustra, y si lleva el nombre de uno de los FENOMENOS la serie
# ocupa uno de sus cupos en vez de sumarse aparte: así fijar una serie no cambia
# el tamaño ni la composición del resto del catálogo. `usada-en-el-texto` es la
# etiqueta para las que no ilustran ningún fenómeno o que no deben ilustrarlo.
SERIES_DEL_LIBRO: dict[str, tuple[str, str]] = {
    "M3007": ("usada-en-el-texto",
              "Capítulo 1: la serie que se acelera y a la que nadie le acierta"),
    "M16834": ("usada-en-el-texto",
               "Capítulo 12: el relleno que el índice de complejidad no ve. "
               "Pasa el filtro de tendencia y estacionalidad por el 14 % que no "
               "es relleno, y por eso el catálogo la mostraba como ejemplar"),
    "Y21804": ("serie-corta",
               "Capítulos 13, 15 y 16 la usan por identificador"),
    "Y22817": ("serie-corta", "Capítulos 15 y 16 la usan por identificador"),
    "M32571": ("cobertura-de-dificultad",
               "Capítulo 16: una de las seis series de la comparación de estimadores"),
    "M6696": ("cobertura-de-dificultad", "Capítulo 16: ídem"),
    "Q5932": ("cobertura-de-dificultad", "Capítulo 16: ídem"),
}

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


def rachas_maximas() -> pd.DataFrame:
    """Racha más larga de valores idénticos consecutivos, por serie.

    Es el descriptor que los 29 de la tesis no tienen: ninguno pregunta si la
    serie repite un valor. Sin él, una serie rellenada con una constante puede
    puntuar alto en tendencia y estacionalidad —las tiene, en el tramo que no es
    relleno— y quedar elegida como ejemplar. Ver `RACHA_MAXIMA_TOLERADA`.

    Se calcula sobre el entrenamiento y sin bucles de Python: una serie está en
    la misma racha que la anterior si comparte identificador y valor, así que
    las rachas son los grupos de un `cumsum` sobre esa condición.
    """
    partes = []
    for frecuencia in FRECUENCIAS:
        archivo = directorio_cache() / "m4" / f"{frecuencia}.parquet"
        if not archivo.exists():
            sys.exit(
                f"Falta la caché {archivo}. Corré primero:\n"
                "  python -m libro._construir_cache"
            )
        d = pd.read_parquet(archivo)
        d = d[d["split"] == "entrenamiento"].sort_values(["serie", "t"])
        y = d["y"].to_numpy()
        ids = d["serie"].astype(str).to_numpy()
        empieza_racha = np.empty(len(y), dtype=bool)
        empieza_racha[0] = True
        empieza_racha[1:] = (ids[1:] != ids[:-1]) | (y[1:] != y[:-1])
        largos = np.bincount(np.cumsum(empieza_racha) - 1)
        rachas = pd.DataFrame({"serie": ids[empieza_racha], "racha": largos})
        partes.append(pd.DataFrame({
            "racha_maxima": rachas.groupby("serie", sort=False)["racha"].max(),
            "n_cache": pd.Series(ids).value_counts(),
        }).reset_index(names="serie"))
    r = pd.concat(partes, ignore_index=True)
    r["racha_relativa"] = r["racha_maxima"] / r["n_cache"]
    return r[["serie", "racha_maxima", "racha_relativa"]]


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
    # La racha máxima sale de los valores, no de los descriptores de la tesis.
    meta = meta.merge(rachas_maximas(), on="serie", how="left")
    sin_racha = int(meta["racha_maxima"].isna().sum())
    if sin_racha:
        sys.exit(f"{sin_racha} series sin racha_maxima: la caché está incompleta.")
    meta["racha_maxima"] = meta["racha_maxima"].astype("int32")

    flotantes = meta.select_dtypes("float64").columns
    meta[flotantes] = meta[flotantes].astype("float32")
    for col in ("categoria", "frecuencia", "dificultad", "etiqueta_m4"):
        if col in meta.columns:
            meta[col] = meta[col].astype("category")
    return meta


# Racha máxima de valores idénticos consecutivos que se tolera en un ejemplar,
# como fracción del largo de entrenamiento. Una serie con un quinto de su
# historia en un solo valor repetido no es una serie: es una serie rellenada, y
# como ejemplar de un fenómeno enseña el relleno en vez del fenómeno.
#
# El umbral sale de medir las 100.000 series: la mediana tiene una racha del
# 1,5 % de su largo, el percentil 99 llega al 11 % y el máximo al 92 %. Con
# 0,20 se excluyen 257 series —el 0,26 %—, y ninguna frecuencia pierde más del
# 0,54 % de las suyas. `M16834`, con 435 de 504 observaciones en el valor
# 10.000 exacto, da 0,86.
#
# El filtro no se aplica a SERIES_DEL_LIBRO: si un capítulo nombra una serie es
# porque la quiere, defecto incluido. `M16834` es justamente ese caso.
RACHA_MAXIMA_TOLERADA = 0.20

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

    # Primero las que el texto nombra: no son negociables. Las que llevan el
    # nombre de un fenómeno consumen uno de sus cupos, que es lo que evita que
    # fijar una serie desplace al resto del catálogo.
    descripciones = {f["nombre"]: f["descripcion"] for f in FENOMENOS}
    fijadas_por_fenomeno: dict[str, int] = {}
    for serie_id, (etiqueta, motivo) in SERIES_DEL_LIBRO.items():
        fila = meta[meta["serie"] == serie_id]
        if fila.empty:
            sys.exit(f"La serie {serie_id} de SERIES_DEL_LIBRO no existe en M4.")
        anotar(fila.iloc[0], etiqueta, descripciones.get(etiqueta, motivo))
        if etiqueta in descripciones:
            fijadas_por_fenomeno[etiqueta] = fijadas_por_fenomeno.get(etiqueta, 0) + 1

    # Las series rellenadas no representan ningún fenómeno más que el relleno.
    elegibles = meta[meta["racha_relativa"] <= RACHA_MAXIMA_TOLERADA]
    descartadas = len(meta) - len(elegibles)
    print(f"  {descartadas} series descartadas por racha de valores idénticos "
          f"(> {RACHA_MAXIMA_TOLERADA:.0%} del largo)")

    for fen in FENOMENOS:
        candidatas = elegibles[fen["filtro"](elegibles)].copy()
        if candidatas.empty:
            print(f"  aviso: sin candidatas para {fen['nombre']}")
            continue
        candidatas["_puntaje"] = fen["puntaje"](candidatas)
        # El desempate va explícito y por identificador. Sin esto la elección
        # entre empatados la decide el algoritmo de ordenamiento —el `quicksort`
        # de pandas no es estable— y basta cambiar cualquier cosa aguas arriba
        # para que el catálogo cambie de series sin motivo. En `serie-corta` hay
        # cientos de series anuales empatadas en 13 observaciones.
        candidatas = candidatas.sort_values(
            ["_puntaje", "serie"], ascending=[False, True], kind="stable")

        # Dos pasadas. La primera reparte entre frecuencias para que el
        # catálogo no quede concentrado en una sola; la segunda llena los cupos
        # que hayan quedado vacíos sin esa restricción.
        tomadas = fijadas_por_fenomeno.get(fen["nombre"], 0)
        frecuencias_vistas: set[str] = set(
            meta.loc[meta["serie"].isin(usadas) & (meta["serie"].isin(
                [s for s, (e, _) in SERIES_DEL_LIBRO.items() if e == fen["nombre"]])),
                "frecuencia"].astype(str))
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
        pozo = elegibles[(elegibles["dificultad"] == nivel)
                         & (~elegibles["serie"].isin(usadas))].copy()
        if pozo.empty:
            continue
        centro = pozo["complexity_index"].median()
        pozo["_dist"] = (pozo["complexity_index"] - centro).abs()
        # Se reparte entre frecuencias también acá, y se desempata igual que
        # arriba: por identificador, no por el orden en que quedaron las filas.
        pozo = pozo.sort_values(["_dist", "serie"], kind="stable")
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
