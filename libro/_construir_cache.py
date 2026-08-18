"""Convierte los CSV transpuestos de M4 en parquet en formato largo.

Los CSV originales de M4 vienen con una serie por fila y una columna por
observación (V1, V2, ...), lo que obliga a leer 215 MB para sacar una serie.
Este script los pasa a formato largo (una fila por observación) y los guarda
en la caché, donde leer una serie cuesta milisegundos.

No es parte de la API del libro: se corre una vez para preparar la caché.

    python -m libro._construir_cache --origen /ruta/a/los/csv/de/M4

Si no se pasa --origen, busca en las rutas de LIBRO_M4_ORIGEN o en las rutas
habituales del proyecto de la tesis.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from libro.datos.rutas import FRECUENCIAS, directorio_cache, origenes_posibles


def _convertir(csv: Path, split: str) -> pd.DataFrame:
    """Lee un CSV transpuesto de M4 y devuelve formato largo sin faltantes."""
    df = pd.read_csv(csv, index_col=0)
    df.index.name = "serie"
    largo = (
        df.stack(future_stack=True)
        .rename("y")
        .reset_index()
        .rename(columns={"level_1": "columna"})
    )
    largo = largo[largo["y"].notna()].copy()
    # V1, V2, ... -> 1, 2, ...
    largo["t"] = largo["columna"].str.removeprefix("V").astype(np.int32)
    largo["split"] = split
    largo["y"] = largo["y"].astype(np.float64)
    return largo[["serie", "t", "y", "split"]]


def construir(origen: Path, destino: Path, frecuencias: list[str] | None = None) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    nombres = frecuencias or list(FRECUENCIAS)

    for nombre in nombres:
        info = FRECUENCIAS[nombre]
        etiqueta = info.etiqueta_m4
        train = origen / f"{etiqueta}-train.csv"
        test = origen / f"{etiqueta}-test.csv"
        if not train.exists():
            print(f"  falta {train.name}, se omite {nombre}")
            continue

        print(f"  {nombre}: leyendo {train.name} ...", flush=True)
        partes = [_convertir(train, "entrenamiento")]
        if test.exists():
            print(f"  {nombre}: leyendo {test.name} ...", flush=True)
            prueba = _convertir(test, "prueba")
            # En el test las columnas reinician en V1: se reindexan a
            # continuación del train para que t sea el tiempo absoluto.
            fin = partes[0].groupby("serie")["t"].max()
            prueba["t"] = prueba["t"] + prueba["serie"].map(fin).astype(np.int32)
            partes.append(prueba)

        largo = pd.concat(partes, ignore_index=True)
        largo = largo.sort_values(["serie", "t"], kind="stable").reset_index(drop=True)
        largo["serie"] = largo["serie"].astype("category")
        largo["split"] = largo["split"].astype("category")

        salida = destino / f"{nombre}.parquet"
        largo.to_parquet(salida, index=False, compression="zstd")
        n_series = largo["serie"].nunique()
        mb = salida.stat().st_size / 1e6
        print(
            f"  {nombre}: {n_series:,} series · {len(largo):,} observaciones"
            f" · {mb:.1f} MB -> {salida.name}",
            flush=True,
        )


def _resolver_origen(explicito: str | None) -> Path:
    if explicito:
        ruta = Path(explicito).expanduser()
        if not ruta.exists():
            sys.exit(f"No existe el directorio de origen: {ruta}")
        return ruta
    for candidato in origenes_posibles():
        if (candidato / "Yearly-train.csv").exists():
            return candidato
    sys.exit(
        "No encontré los CSV de M4. Pasá --origen con el directorio que "
        "contiene Yearly-train.csv, Monthly-train.csv, etc."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origen", default=None)
    parser.add_argument("--destino", default=None)
    parser.add_argument("--frecuencias", nargs="*", default=None)
    args = parser.parse_args()

    origen = _resolver_origen(args.origen)
    destino = Path(args.destino).expanduser() if args.destino else directorio_cache() / "m4"
    print(f"Origen : {origen}")
    print(f"Destino: {destino}")
    construir(origen, destino, args.frecuencias)


if __name__ == "__main__":
    main()
