"""Exporta a CSV las series que necesitan los widgets.

Los widgets de shinylive corren en el navegador y no pueden importar
`libro.datos`: su sistema de archivos es virtual y lleva solo lo que se le
incluye. Así que las series que usan se exportan a CSV, se versionan, y el
bloque del widget las incluye con `{{< include >}}`.

Hay que correrlo **antes** de compilar, porque Quarto resuelve los `include`
antes de ejecutar el código. Está en el `Makefile` como `make datos-widgets`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from libro.datos import cargar

DESTINO = Path(__file__).resolve().parent.parent / "capitulos" / "datos"

# Qué series necesita cada widget. La clave es el archivo; el valor, la lista
# de series con la etiqueta corta que el widget muestra al lector.
WIDGETS: dict[str, list[tuple[str, str]]] = {
    "cap01_series.csv": [
        ("D1", "tendencia limpia"),
        ("M35927", "estacionalidad marcada"),
        ("D2039", "caminata aleatoria"),
        ("M32692", "quiebre de nivel"),
    ],
    # Capítulo 2: una serie horaria, para practicar remuestreo en el navegador.
    "cap02_horaria.csv": [
        ("H317", "horaria con ciclo diario"),
    ],
    # Capítulo 4: cuatro series estacionales para el widget de STL. Todas con
    # m > 1, porque sin estacionalidad el deslizador no tiene qué mover.
    "cap04_estacionales.csv": [
        ("M35927", "estacionalidad marcada"),
        ("M3007", "estacionalidad débil"),
        ("Q15481", "amplitud creciente"),
        ("M32692", "quiebre de nivel"),
    ],
}


def exportar() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for archivo, series in WIDGETS.items():
        partes = []
        for serie_id, etiqueta in series:
            s = cargar(serie_id)
            df = s.a_frame()
            df["etiqueta"] = etiqueta
            df["m"] = s.periodo_estacional
            # Las series largas se recortan: un widget no necesita 9.000
            # puntos y el CSV viaja embebido en el HTML.
            if (s.n) > 400:
                corte = s.entrenamiento.index[-400]
                df = df[df["ds"] >= corte]
            partes.append(df)
        salida = pd.concat(partes, ignore_index=True)
        salida["y"] = salida["y"].round(4)
        ruta = DESTINO / archivo
        salida.to_csv(ruta, index=False)
        print(f"{ruta.relative_to(DESTINO.parent.parent)}: "
              f"{len(salida):,} filas · {ruta.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    exportar()
