"""Trae al repositorio las tablas de resultados de la tesis que el capítulo 22 cita.

Son tablas chicas y ya agregadas: no viajan las 4.773 series, solo los resúmenes.
"""
from pathlib import Path
import pandas as pd

TESIS = Path.home() / "Library/CloudStorage/OneDrive-Personal/MAESTRIA2025/TESIS"
DESTINO = Path("libro/datos/tesis")
DESTINO.mkdir(parents=True, exist_ok=True)

# --- 1. Rangos de Friedman de los 27 modelos, con la prueba de Nemenyi
friedman = pd.read_excel(TESIS / "friedman_rangos.xlsx")
friedman.to_parquet(DESTINO / "friedman.parquet", index=False)
print("friedman.parquet", friedman.shape)

# --- 2. OWA de los modelos que superan a Naive2 (sección 3 de OBSERVACIONES)
owa = pd.DataFrame([
    {"modelo": "ARIMA",        "sMAPE": 13.33, "MASE": 1.71, "OWA": 0.936},
    {"modelo": "SARIMA",       "sMAPE": 13.35, "MASE": 1.71, "OWA": 0.938},
    {"modelo": "LassoLars",    "sMAPE": 13.52, "MASE": 1.82, "OWA": 0.974},
    {"modelo": "Lineal",       "sMAPE": 13.47, "MASE": 1.85, "OWA": 0.978},
    {"modelo": "Holt-Winters", "sMAPE": 14.32, "MASE": 1.04, "OWA": 0.995},
    {"modelo": "ETS",          "sMAPE": 14.52, "MASE": 1.78, "OWA": 0.998},
    {"modelo": "Naive2",       "sMAPE": 13.73, "MASE": 1.90, "OWA": 1.000},
])
owa.to_parquet(DESTINO / "owa.parquet", index=False)
print("owa.parquet", owa.shape)

# --- 3. OWA en Hourly contra el global (sección 3.1)
horaria = pd.DataFrame([
    {"modelo": "sNaive",          "OWA horaria": 0.626, "OWA global": 1.007},
    {"modelo": "ARIMA / SARIMA",  "OWA horaria": 0.724, "OWA global": 0.936},
    {"modelo": "ConvNet 1D",      "OWA horaria": 0.762, "OWA global": 1.609},
    {"modelo": "Perceptrón",      "OWA horaria": 0.768, "OWA global": 1.543},
    {"modelo": "Transformer",     "OWA horaria": 0.807, "OWA global": 1.419},
])
horaria.to_parquet(DESTINO / "horaria.parquet", index=False)
print("horaria.parquet", horaria.shape)

# --- 4. Varianza por semilla: 90 series x 5 semillas x 5 redes (sección 4)
semillas = pd.DataFrame([
    {"modelo": "Transformer",  "sMAPE": 13.15, "desvío": 1.79, "CV %": 16.8},
    {"modelo": "Perceptrón",   "sMAPE": 15.05, "desvío": 0.80, "CV %":  5.5},
    {"modelo": "LSTM",         "sMAPE": 15.13, "desvío": 1.26, "CV %": 10.1},
    {"modelo": "LSTM-ConvNet", "sMAPE": 15.34, "desvío": 1.53, "CV %": 11.2},
    {"modelo": "ConvNet 1D",   "sMAPE": 15.48, "desvío": 1.23, "CV %":  9.2},
])
semillas.to_parquet(DESTINO / "semillas.parquet", index=False)
print("semillas.parquet", semillas.shape)

# --- 5. El ganador cambia con la semilla, por frecuencia (sección 4)
por_frecuencia = pd.DataFrame([
    {"frecuencia": "anual",      "el ganador cambia %": 50, "brecha 1º-2º": 1.90,
     "ruido de semilla": 5.00},
    {"frecuencia": "trimestral", "el ganador cambia %": 70, "brecha 1º-2º": 1.86,
     "ruido de semilla": 3.72},
    {"frecuencia": "mensual",    "el ganador cambia %": 83, "brecha 1º-2º": 0.64,
     "ruido de semilla": 2.57},
])
por_frecuencia["razón"] = (por_frecuencia["ruido de semilla"]
                          / por_frecuencia["brecha 1º-2º"]).round(1)
por_frecuencia.to_parquet(DESTINO / "semillas_por_frecuencia.parquet", index=False)
print("semillas_por_frecuencia.parquet", por_frecuencia.shape)

# --- 6. Validación externa: Naive2 contra los valores publicados de M4 (6.1)
naive2 = pd.DataFrame([
    {"frecuencia": "anual",      "calculado": 16.342, "publicado en M4": 16.342},
    {"frecuencia": "trimestral", "calculado": 11.024, "publicado en M4": 11.012},
    {"frecuencia": "mensual",    "calculado": 14.385, "publicado en M4": 14.427},
    {"frecuencia": "semanal",    "calculado":  9.161, "publicado en M4":  9.161},
    {"frecuencia": "diaria",     "calculado":  3.045, "publicado en M4":  3.045},
    {"frecuencia": "horaria",    "calculado": 18.616, "publicado en M4": 18.383},
    {"frecuencia": "todas",      "calculado": 13.548, "publicado en M4": 13.564},
])
naive2["diferencia"] = (naive2["calculado"] - naive2["publicado en M4"]).round(3)
naive2.to_parquet(DESTINO / "naive2_validacion.parquet", index=False)
print("naive2_validacion.parquet", naive2.shape)

# --- 7. Costo computacional de reejecutar el pipeline completo (7.6)
costo = pd.DataFrame([
    {"etapa": "PCA e índice de complejidad", "minutos": 0.8},
    {"etapa": "clustering", "minutos": 2.0},
    {"etapa": "entropías", "minutos": 994.0},
    {"etapa": "errores de pronóstico de la muestra", "minutos": 203.0},
    {"etapa": "validación del índice", "minutos": 0.1},
])
costo["% del total"] = (100 * costo["minutos"] / costo["minutos"].sum()).round(1)
costo.to_parquet(DESTINO / "costo.parquet", index=False)
print("costo.parquet", costo.shape)

# --- 8. Composición de la muestra contra la población de M4 (5.5)
muestra = pd.DataFrame([
    {"frecuencia": "diaria",  "en la muestra %": 21.0, "en M4 %": 4.2},
    {"frecuencia": "horaria", "en la muestra %":  8.7, "en M4 %": 0.4},
    {"frecuencia": "mensual", "en la muestra %": 21.0, "en M4 %": 48.0},
])
muestra["sobre-representación"] = (muestra["en la muestra %"]
                                   / muestra["en M4 %"]).round(1)
muestra.to_parquet(DESTINO / "muestra.parquet", index=False)
print("muestra.parquet", muestra.shape)

for p in sorted(DESTINO.glob("*.parquet")):
    print(f"  {p.name}: {p.stat().st_size / 1024:.1f} KB")
