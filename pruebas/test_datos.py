"""Pruebas del módulo de datos.

Lo que se verifica acá no es que el código no explote, sino que los datos que
el libro va a usar sean los de la competencia: los horizontes oficiales, los
períodos estacionales de M4 y las particiones sin contaminación.
"""

from __future__ import annotations

import pandas as pd
import pytest

from libro.datos import SerieM4, cargar, catalogo, fenomenos, metadatos
from libro.datos.rutas import FRECUENCIAS, NIVELES_DIFICULTAD


# --- lo básico -------------------------------------------------------------


def test_cargar_por_identificador():
    s = cargar("M3007")
    assert isinstance(s, SerieM4)
    assert s.id == "M3007"
    assert s.frecuencia == "mensual"


def test_identificador_desconocido_avisa_claro():
    with pytest.raises(ValueError, match="Y1, Q10, M3007"):
        cargar("ZZZ9")


def test_cargar_conjunto_devuelve_lista():
    series = cargar(frecuencia="mensual", n=3)
    assert isinstance(series, list) and len(series) == 3
    assert all(s.frecuencia == "mensual" for s in series)


def test_sin_n_devuelve_una_sola_serie():
    assert isinstance(cargar(frecuencia="anual"), SerieM4)


def test_la_eleccion_es_reproducible():
    a = [s.id for s in cargar(frecuencia="mensual", n=4)]
    b = [s.id for s in cargar(frecuencia="mensual", n=4)]
    assert a == b


# --- las convenciones de la competencia ------------------------------------


@pytest.mark.parametrize("nombre,info", FRECUENCIAS.items())
def test_horizonte_y_estacionalidad_son_los_de_m4(nombre, info):
    """Los horizontes de M4: 6, 8, 18, 13, 14, 48. Y m=1 en Weekly y Daily."""
    cat = catalogo()
    if nombre not in set(cat["frecuencia"]):
        pytest.skip(f"el catálogo no tiene series {nombre}")
    s = cargar(frecuencia=nombre)
    assert s.horizonte == info.horizonte
    assert s.periodo_estacional == info.periodo_estacional
    assert len(s.prueba) == info.horizonte


def test_weekly_y_daily_no_son_estacionales_para_m4():
    """Trampa documentada: lo natural sería 52 y 7, M4 usa 1."""
    assert FRECUENCIAS["semanal"].periodo_estacional == 1
    assert FRECUENCIAS["semanal"].periodo_natural == 52
    assert FRECUENCIAS["diaria"].periodo_estacional == 1
    assert FRECUENCIAS["diaria"].periodo_natural == 7


def test_la_prueba_no_se_solapa_con_el_entrenamiento():
    for s in cargar(n=8):
        assert s.entrenamiento.index.max() < s.prueba.index.min()
        assert len(s.entrenamiento.index.intersection(s.prueba.index)) == 0


def test_no_hay_faltantes_ni_indices_desordenados():
    for s in cargar(n=8):
        assert s.entrenamiento.notna().all()
        assert s.prueba.notna().all()
        assert s.entrenamiento.index.is_monotonic_increasing
        assert s.completa.index.is_monotonic_increasing


def test_la_serie_completa_es_la_suma_de_las_partes():
    s = cargar("M3007")
    assert len(s.completa) == len(s.entrenamiento) + len(s.prueba)


# --- catálogo y metadatos --------------------------------------------------


def test_el_catalogo_cubre_el_espectro_de_dificultad():
    cat = catalogo()
    for nivel in NIVELES_DIFICULTAD:
        assert (cat["dificultad"] == nivel).sum() >= 4, f"falta cubrir {nivel}"


def test_el_catalogo_cubre_los_fenomenos_prometidos():
    esperados = {
        "tendencia-limpia",
        "estacionalidad-marcada",
        "caminata-aleatoria",
        "quiebre-de-nivel",
        "cambio-de-varianza",
        "serie-corta",
        "serie-larga",
    }
    assert esperados <= set(catalogo()["fenomeno"])


def test_pedir_una_serie_dificil_da_una_dificil():
    s = cargar(dificultad="alta")
    assert s.dificultad == "alta"
    mediana = metadatos()["complexity_index"].median()
    assert s.complejidad > mediana


def test_pedir_por_fenomeno():
    s = cargar(fenomeno="caminata-aleatoria")
    assert s.fenomeno == "caminata-aleatoria"


def test_fenomeno_inexistente_lista_los_validos():
    with pytest.raises(ValueError, match="Los disponibles son"):
        cargar(fenomeno="tendencia-inventada")


def test_las_series_que_el_texto_nombra_viajan_en_el_repositorio():
    """El libro tiene que compilar sin conexión.

    Si un capítulo pide una serie por identificador y esa serie no está en el
    paquete curado, el módulo intenta bajar los CSV de M4 —cientos de
    megabytes— al compilar. Pasó con M3007 en el capítulo 1.
    """
    from libro._construir_catalogo import SERIES_DEL_LIBRO

    faltan = sorted(set(SERIES_DEL_LIBRO) - set(catalogo()["serie"]))
    assert not faltan, (
        f"Estas series las nombra el texto pero no están en el catálogo: "
        f"{faltan}. Corré `make catalogo`."
    )


def test_las_series_fijadas_conservan_la_etiqueta_declarada():
    """Fijar una serie no debe cambiarle el fenómeno que ilustra.

    `SERIES_DEL_LIBRO` declara con qué etiqueta viaja cada serie fijada, y esa
    etiqueta es la que la prosa de los capítulos da por cierta: el 15 dice que
    `Y21804` es una serie corta, el 12 dice que `M16834` está por el texto y no
    por ilustrar nada.
    """
    from libro._construir_catalogo import SERIES_DEL_LIBRO

    cat = catalogo().set_index("serie")["fenomeno"]
    mal = {
        serie: (etiqueta, cat[serie])
        for serie, (etiqueta, _) in SERIES_DEL_LIBRO.items()
        if cat[serie] != etiqueta
    }
    assert not mal, f"etiqueta declarada ≠ etiqueta del catálogo: {mal}"


def test_ninguna_serie_rellenada_ilustra_un_fenomeno():
    """El filtro que dejó a `M16834` afuera sigue puesto.

    Una serie con un quinto de su historia en un solo valor repetido enseña el
    relleno, no el fenómeno. Ver el capítulo 12.
    """
    from libro._construir_catalogo import RACHA_MAXIMA_TOLERADA

    meta = metadatos().set_index("serie")
    cat = catalogo()
    ejemplares = cat[cat["fenomeno"] != "usada-en-el-texto"]["serie"]
    rachas = meta.loc[ejemplares, "racha_relativa"]
    culpables = rachas[rachas > RACHA_MAXIMA_TOLERADA]
    assert culpables.empty, (
        f"estas ilustran un fenómeno con una racha demasiado larga:\n{culpables}"
    )


def test_sin_descarga_no_se_cuelga_sino_que_avisa(monkeypatch):
    """Con LIBRO_SIN_DESCARGA puesta, nada intenta bajar cientos de megabytes."""
    from libro.datos.rutas import descargas_permitidas

    monkeypatch.setenv("LIBRO_SIN_DESCARGA", "1")
    assert descargas_permitidas() is False
    monkeypatch.delenv("LIBRO_SIN_DESCARGA")
    assert descargas_permitidas() is True


def test_metadatos_tiene_las_99935_series():
    meta = metadatos()
    assert len(meta) == 99_935
    assert meta["serie"].is_unique


def test_todas_las_series_del_catalogo_tienen_valores():
    for serie_id in catalogo()["serie"]:
        s = cargar(serie_id)
        assert s.n > 0 and len(s.prueba) == s.horizonte


def test_fenomenos_es_una_tabla_legible():
    tabla = fenomenos()
    assert {"fenomeno", "descripcion_fenomeno", "series"} <= set(tabla.columns)
    assert len(tabla) >= 7


# --- formato para las bibliotecas ------------------------------------------


def test_a_frame_usa_las_columnas_de_statsforecast():
    df = cargar("M3007").a_frame()
    assert list(df.columns) == ["unique_id", "ds", "y", "split"]
    assert pd.api.types.is_datetime64_any_dtype(df["ds"])
    assert df["unique_id"].nunique() == 1


def test_a_frame_puede_dejar_afuera_la_prueba():
    df = cargar("M3007").a_frame(incluir_prueba=False)
    assert set(df["split"]) == {"entrenamiento"}


# ---------------------------------------------------------------------------
# Las tablas de resultados de la tesis que cita el capítulo 22
# ---------------------------------------------------------------------------


def test_las_tablas_de_tesis_viajan_en_el_repositorio():
    """El capítulo 22 no puede entrenar redes: cita resultados ya calculados."""
    from libro.datos import TABLAS_DE_TESIS, resultados_tesis

    for nombre in TABLAS_DE_TESIS:
        tabla = resultados_tesis(nombre)
        assert len(tabla) > 0, f"la tabla {nombre} está vacía"


def test_el_ranking_de_friedman_tiene_los_27_modelos():
    from libro.datos import resultados_tesis

    friedman = resultados_tesis("friedman")
    for metrica in ("sMAPE", "MASE"):
        sub = friedman[friedman["metrica"] == metrica]
        assert len(sub) == 27, f"{metrica} tiene {len(sub)} modelos y no 27"
        assert sorted(sub["puesto"]) == list(range(1, 28))


def test_resultados_tesis_rechaza_un_nombre_desconocido():
    from libro.datos import resultados_tesis

    with pytest.raises(KeyError, match="No conozco la tabla"):
        resultados_tesis("no-existe")
