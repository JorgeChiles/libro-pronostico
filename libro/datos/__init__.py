"""Acceso a las series de la competencia M4.

    from libro.datos import cargar

    s = cargar("M3007")                      # una serie por identificador
    s = cargar(frecuencia="mensual", n=20)   # un conjunto
    s = cargar(dificultad="alta")            # una serie difícil de verdad
    s = cargar(fenomeno="quiebre-de-nivel")  # una serie que ilustra un fenómeno

Cada serie llega como un objeto `SerieM4` con la partición oficial de la
competencia ya hecha y sus metadatos:

    s.entrenamiento        # pandas.Series con índice de fechas
    s.prueba               # las h observaciones que M4 reserva
    s.horizonte            # h, fijado por la competencia
    s.periodo_estacional   # m según M4 (ojo: Weekly y Daily valen 1)
    s.categoria            # Macro, Micro, Finance, Industry, Demographic, Other
    s.complejidad          # índice de complejidad estructural
    s.dificultad           # su cuartil: baja, media_baja, media_alta, alta

De dónde salen los datos, en este orden:

1. **El catálogo curado**, que viaja en el repositorio. Son 33 series y cubren
   todos los ejemplos del libro. Funciona sin conexión y sin caché.
2. **La caché local** en `~/.cache/libro-pronostico/m4/`, si existe.
3. **Descarga**, una sola vez, y guarda en la caché.

El libro entero compila con el paso 1. Los pasos 2 y 3 están para cuando el
lector quiera salirse del catálogo y explorar las 100.000 series.
"""

from __future__ import annotations

import shutil
import urllib.request
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from libro.datos.rutas import (
    ALIAS_FRECUENCIA,
    FRECUENCIAS,
    NIVELES_DIFICULTAD,
    URL_M4,
    Frecuencia,
    descargas_permitidas,
    directorio_cache,
    directorio_curado,
    directorio_tesis,
    frecuencia_de_id,
    normalizar_frecuencia,
    origenes_posibles,
)

__all__ = ["cargar", "catalogo", "metadatos", "SerieM4", "fenomenos",
           "resultados_tesis"]

SEMILLA = 42


# ---------------------------------------------------------------------------
# El objeto que devuelve cargar()
# ---------------------------------------------------------------------------


@dataclass
class SerieM4:
    """Una serie de M4 con su partición oficial y sus metadatos."""

    id: str
    entrenamiento: pd.Series
    prueba: pd.Series
    frecuencia: str
    horizonte: int
    periodo_estacional: int
    periodo_natural: int
    categoria: str
    complejidad: float = float("nan")
    dificultad: str = ""
    fenomeno: str = ""
    descriptores: dict = field(default_factory=dict, repr=False)

    @property
    def completa(self) -> pd.Series:
        """Entrenamiento y prueba concatenados."""
        return pd.concat([self.entrenamiento, self.prueba])

    @property
    def n(self) -> int:
        return len(self.entrenamiento)

    def a_frame(self, *, incluir_prueba: bool = True) -> pd.DataFrame:
        """Formato largo, el que esperan statsforecast y sklearn.

        Columnas: `unique_id`, `ds`, `y`, `split`.
        """
        partes = [self.entrenamiento.rename("y").to_frame().assign(split="entrenamiento")]
        if incluir_prueba:
            partes.append(self.prueba.rename("y").to_frame().assign(split="prueba"))
        df = pd.concat(partes)
        df.index.name = "ds"
        return df.reset_index().assign(unique_id=self.id)[
            ["unique_id", "ds", "y", "split"]
        ]

    def __repr__(self) -> str:  # pragma: no cover - solo presentación
        etiqueta = f", {self.fenomeno}" if self.fenomeno else ""
        return (
            f"SerieM4({self.id}, {self.frecuencia}, n={self.n}, "
            f"h={self.horizonte}, m={self.periodo_estacional}, "
            f"{self.categoria}, dificultad={self.dificultad}{etiqueta})"
        )


# ---------------------------------------------------------------------------
# Metadatos y catálogo
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def metadatos() -> pd.DataFrame:
    """Una fila por serie de M4 (99.935) con descriptores y complejidad.

    Son 99.935 y no 100.000: el pipeline que calculó los descriptores descarta
    65 series semanales demasiado cortas para calcularlos todos.
    """
    ruta = directorio_curado() / "metadatos.parquet"
    if not ruta.exists():
        raise FileNotFoundError(
            f"No encuentro {ruta}. Se genera con:\n"
            "  python -m libro._construir_catalogo"
        )
    return pd.read_parquet(ruta)


@lru_cache(maxsize=1)
def catalogo() -> pd.DataFrame:
    """Las series curadas del libro, una fila por serie, con su fenómeno."""
    ruta = directorio_curado() / "catalogo.parquet"
    if not ruta.exists():
        raise FileNotFoundError(
            f"No encuentro {ruta}. Se genera con:\n"
            "  python -m libro._construir_catalogo"
        )
    return pd.read_parquet(ruta)


TABLAS_DE_TESIS = {
    "friedman": "Rangos de Friedman de los 27 modelos, con la prueba de Nemenyi",
    "owa": "OWA de los modelos que superan a Naive2",
    "horaria": "OWA en la frecuencia horaria contra el global",
    "semillas": "sMAPE y variabilidad de cinco redes sobre cinco semillas",
    "semillas_por_frecuencia": "Cuántas veces cambia el ganador según la frecuencia",
}


def resultados_tesis(nombre: str) -> pd.DataFrame:
    """Una tabla de resultados de la tesis. Ver TABLAS_DE_TESIS para los nombres.

    Son resúmenes ya agregados sobre 4.773 series, no las series en sí. El
    capítulo 22 los cita porque el libro no puede entrenar redes al compilar.
    """
    if nombre not in TABLAS_DE_TESIS:
        disponibles = ", ".join(sorted(TABLAS_DE_TESIS))
        raise KeyError(f"No conozco la tabla {nombre!r}. Hay: {disponibles}")
    ruta = directorio_tesis() / f"{nombre}.parquet"
    if not ruta.exists():
        raise FileNotFoundError(
            f"No encuentro {ruta}. Se genera con:\n"
            "  python -m libro._construir_tesis"
        )
    return pd.read_parquet(ruta)


def fenomenos() -> pd.DataFrame:
    """Qué fenómenos cubre el catálogo y con cuántas series cada uno."""
    cat = catalogo()
    return (
        cat.groupby(["fenomeno", "descripcion_fenomeno"], as_index=False)
        .agg(series=("serie", "count"), ejemplos=("serie", lambda s: ", ".join(sorted(s))))
        .sort_values("fenomeno")
        .reset_index(drop=True)
    )


@lru_cache(maxsize=1)
def _valores_catalogo() -> pd.DataFrame:
    ruta = directorio_curado() / "catalogo_valores.parquet"
    if not ruta.exists():
        raise FileNotFoundError(
            f"No encuentro {ruta}. Se genera con:\n"
            "  python -m libro._construir_catalogo"
        )
    df = pd.read_parquet(ruta)
    df["serie"] = df["serie"].astype(str)
    return df


# ---------------------------------------------------------------------------
# Obtener las observaciones de una serie
# ---------------------------------------------------------------------------


@lru_cache(maxsize=8)
def _parquet_frecuencia(nombre: str) -> pd.DataFrame:
    """Carga (bajando si hace falta) el parquet de una frecuencia completa."""
    archivo = directorio_cache() / "m4" / f"{nombre}.parquet"
    if not archivo.exists():
        _preparar_frecuencia(nombre, archivo)
    df = pd.read_parquet(archivo)
    df["serie"] = df["serie"].astype(str)
    return df


def _preparar_frecuencia(nombre: str, destino: Path) -> None:
    """Construye la caché de una frecuencia: desde CSV local o bajándolo."""
    info = FRECUENCIAS[nombre]
    destino.parent.mkdir(parents=True, exist_ok=True)

    origen = None
    for candidato in origenes_posibles():
        if (candidato / f"{info.etiqueta_m4}-train.csv").exists():
            origen = candidato
            break

    if origen is None:
        if not descargas_permitidas():
            raise RuntimeError(
                f"Para tener la frecuencia {nombre!r} completa habría que bajar "
                f"los CSV de M4 —cientos de megabytes— y las descargas están "
                f"desactivadas por la variable LIBRO_SIN_DESCARGA.\n\n"
                f"Si esto ocurrió al compilar el libro, es un error del "
                f"capítulo: está pidiendo una serie que no viaja en el "
                f"repositorio. Agregala a SERIES_DEL_LIBRO en "
                f"libro/_construir_catalogo.py y corré `make catalogo`.\n\n"
                f"Si la pediste a propósito, corré `make datos` una vez."
            )
        origen = directorio_cache() / "m4_csv"
        origen.mkdir(parents=True, exist_ok=True)
        for parte in ("train", "test"):
            archivo = origen / f"{info.etiqueta_m4}-{parte}.csv"
            if archivo.exists():
                continue
            url = f"{URL_M4}{parte.capitalize()}/{info.etiqueta_m4}-{parte}.csv"
            print(
                f"Bajando {info.etiqueta_m4}-{parte}.csv desde el repositorio de "
                f"M4. Es un archivo grande y se baja una sola vez.",
                flush=True,
            )
            with urllib.request.urlopen(url) as respuesta, archivo.open("wb") as salida:
                shutil.copyfileobj(respuesta, salida)

    from libro._construir_cache import construir

    construir(origen, destino.parent, [nombre])


def _observaciones(serie_id: str) -> pd.DataFrame:
    """Devuelve las filas (t, y, split) de una serie, de donde estén."""
    curado = _valores_catalogo()
    filas = curado[curado["serie"] == serie_id]
    if not filas.empty:
        return filas

    frecuencia = frecuencia_de_id(serie_id).nombre
    df = _parquet_frecuencia(frecuencia)
    filas = df[df["serie"] == serie_id]
    if filas.empty:
        raise KeyError(f"La serie {serie_id!r} no existe en M4.")
    return filas


# ---------------------------------------------------------------------------
# Índice de fechas
# ---------------------------------------------------------------------------


def _fecha_inicio(valor, info: Frecuencia) -> pd.Timestamp:
    """Interpreta la fecha de inicio que declara M4, con respaldo si es inválida.

    Las fechas de M4 son irregulares: algunas caen en 1750, otras usan formatos
    ambiguos. El libro las usa para tener un eje temporal legible, no como dato
    sustantivo. Si no se puede interpretar, se usa una fecha de respaldo y se
    sigue: el análisis no depende de ella.
    """
    respaldo = {"anual": "1970-01-01", "trimestral": "1990-01-01",
                "mensual": "1990-01-01", "semanal": "2000-01-03",
                "diaria": "2000-01-01", "horaria": "2015-01-01"}[info.nombre]
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return pd.Timestamp(respaldo)
    fecha = pd.to_datetime(valor, dayfirst=True, errors="coerce")
    if pd.isna(fecha) or not (pd.Timestamp("1900-01-01") <= fecha <= pd.Timestamp("2030-01-01")):
        return pd.Timestamp(respaldo)
    return fecha


def _indice(inicio: pd.Timestamp, n: int, info: Frecuencia) -> pd.DatetimeIndex:
    """Índice de fechas de la serie.

    Se usa resolución de segundos y no de nanosegundos: hay series anuales de
    M4 con cientos de observaciones que, partiendo de la fecha declarada, se
    pasan del año 2262 —el techo de los nanosegundos— y `date_range` falla.
    """
    return pd.date_range(
        start=inicio, periods=n, freq=info.frecuencia_pandas, unit="s"
    )


# ---------------------------------------------------------------------------
# cargar()
# ---------------------------------------------------------------------------


def _construir(serie_id: str, fila_meta: pd.Series | None,
               fenomeno: str = "") -> SerieM4:
    info = frecuencia_de_id(serie_id)
    obs = _observaciones(serie_id).sort_values("t")

    entrenamiento = obs[obs["split"] == "entrenamiento"]
    prueba = obs[obs["split"] == "prueba"]

    inicio = _fecha_inicio(
        fila_meta["fecha_inicio"] if fila_meta is not None else None, info
    )
    idx = _indice(inicio, len(obs), info)

    y_train = pd.Series(entrenamiento["y"].to_numpy(), index=idx[: len(entrenamiento)],
                        name=serie_id)
    y_test = pd.Series(prueba["y"].to_numpy(), index=idx[len(entrenamiento):],
                       name=serie_id)

    descriptores: dict = {}
    if fila_meta is not None:
        omitir = {"serie", "fenomeno", "descripcion_fenomeno"}
        descriptores = {k: v for k, v in fila_meta.items() if k not in omitir}

    return SerieM4(
        id=serie_id,
        entrenamiento=y_train,
        prueba=y_test,
        frecuencia=info.nombre,
        horizonte=info.horizonte,
        periodo_estacional=info.periodo_estacional,
        periodo_natural=info.periodo_natural,
        categoria=str(fila_meta["categoria"]) if fila_meta is not None else "",
        complejidad=float(fila_meta["complexity_index"]) if fila_meta is not None
        else float("nan"),
        dificultad=str(fila_meta["dificultad"]) if fila_meta is not None else "",
        fenomeno=fenomeno,
        descriptores=descriptores,
    )


def _meta_de(serie_id: str) -> pd.Series | None:
    meta = metadatos()
    filas = meta[meta["serie"] == serie_id]
    return None if filas.empty else filas.iloc[0]


def cargar(
    identificador: str | None = None,
    *,
    frecuencia: str | None = None,
    dificultad: str | None = None,
    fenomeno: str | None = None,
    categoria: str | None = None,
    n: int | None = None,
    solo_catalogo: bool | None = None,
    semilla: int = SEMILLA,
) -> SerieM4 | list[SerieM4]:
    """Carga una serie de M4, o un conjunto.

    Parámetros
    ----------
    identificador
        El id de M4: `"M3007"`, `"Y1"`, `"H100"`. Si se pasa, se ignora el resto.
    frecuencia
        `"anual"`, `"trimestral"`, `"mensual"`, `"semanal"`, `"diaria"`,
        `"horaria"`. También acepta los nombres de la competencia (`"Monthly"`).
    dificultad
        `"baja"`, `"media_baja"`, `"media_alta"` o `"alta"`, según el cuartil
        del índice de complejidad estructural.
    fenomeno
        Una de las etiquetas del catálogo: `"tendencia-limpia"`,
        `"estacionalidad-marcada"`, `"caminata-aleatoria"`,
        `"quiebre-de-nivel"`, `"cambio-de-varianza"`, `"serie-corta"`,
        `"serie-larga"`... `libro.datos.fenomenos()` los lista todos.
    categoria
        `"Macro"`, `"Micro"`, `"Finance"`, `"Industry"`, `"Demographic"`, `"Other"`.
    n
        Cuántas series devolver. Sin `n`, devuelve una sola serie (no una lista).
    solo_catalogo
        Sin especificar, decide solo: usa el catálogo curado —que está en el
        repositorio y no requiere descargas— siempre que alcance para lo
        pedido, y recién si no alcanza pasa a las 99.935 series. Con `True`
        nunca sale del catálogo; con `False` va directo a la población
        completa, que puede requerir bajar datos la primera vez.
    semilla
        Para que la elección sea reproducible.

    Devuelve
    --------
    `SerieM4` si no se pasó `n`; una lista de `SerieM4` si se pasó.
    """
    if identificador is not None:
        serie_id = str(identificador).strip().upper()
        frecuencia_de_id(serie_id)  # valida el prefijo
        fila = _meta_de(serie_id)
        cat = catalogo()
        marca = cat[cat["serie"] == serie_id]
        etiqueta = str(marca.iloc[0]["fenomeno"]) if not marca.empty else ""
        return _construir(serie_id, fila, etiqueta)

    if fenomeno is not None and solo_catalogo is False:
        raise ValueError(
            "El fenómeno es una etiqueta del catálogo curado del libro, así que "
            "no se puede combinar con solo_catalogo=False."
        )

    def filtrar(base: pd.DataFrame) -> pd.DataFrame:
        if frecuencia is not None:
            base = base[base["frecuencia"] == normalizar_frecuencia(frecuencia).nombre]
        if dificultad is not None:
            nivel = str(dificultad).strip().lower()
            if nivel not in NIVELES_DIFICULTAD:
                validas = ", ".join(NIVELES_DIFICULTAD)
                raise ValueError(
                    f"dificultad debe ser una de: {validas}. Recibí {dificultad!r}."
                )
            base = base[base["dificultad"] == nivel]
        if fenomeno is not None:
            etiqueta = str(fenomeno).strip().lower()
            base = base[base["fenomeno"] == etiqueta]
            if base.empty:
                disponibles = ", ".join(sorted(catalogo()["fenomeno"].unique()))
                raise ValueError(
                    f"No hay series con el fenómeno {fenomeno!r}. "
                    f"Los disponibles son: {disponibles}."
                )
        if categoria is not None:
            base = base[base["categoria"].str.lower() == str(categoria).strip().lower()]
        return base

    cuantas = 1 if n is None else int(n)

    # Preferencia por el catálogo: está en el repositorio y no baja nada. Solo
    # se recurre a las 99.935 series si el catálogo no alcanza.
    if solo_catalogo is False:
        base = filtrar(metadatos())
    else:
        base = filtrar(catalogo())
        if len(base) < cuantas and solo_catalogo is None:
            base = filtrar(metadatos())

    if base.empty:
        raise ValueError(
            "Ninguna serie cumple esos filtros. Probá con menos restricciones."
        )
    if cuantas > len(base):
        raise ValueError(
            f"Pediste {cuantas} series y solo hay {len(base)} que cumplan los filtros."
        )

    elegidas = base.sample(n=cuantas, random_state=semilla)
    series = [
        _construir(
            str(fila["serie"]),
            fila if "complexity_index" in fila.index else _meta_de(str(fila["serie"])),
            str(fila.get("fenomeno", "")),
        )
        for _, fila in elegidas.iterrows()
    ]
    return series[0] if n is None else series
