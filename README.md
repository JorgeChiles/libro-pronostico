# Pronóstico de series de tiempo con Python

Libro en línea, gratuito y con todo el código ejecutable, sobre pronóstico de
series de tiempo: de los métodos estadísticos clásicos al aprendizaje
automático. En español.

Cubre el mismo recorrido que *Forecasting: Principles and Practice* de Hyndman y
Athanasopoulos, en Python en vez de R, y le agrega una segunda parte completa
sobre aprendizaje automático aplicado a series.

Todos los ejemplos usan series reales de la competencia **M4** —100.000 series
con la partición de entrenamiento y prueba oficial—, no datos inventados.

## Cómo compilarlo

Hace falta [Quarto](https://quarto.org) **1.9.38** y Python 3.13.

```bash
make entorno   # crea ~/.venvs/libro, instala dependencias y registra el kernel
make libro     # compila el libro en _site/
make ver       # compila y abre con recarga automática
```

Compilar pasa siempre por `make` y no por `quarto render` a mano: Quarto
necesita tres cosas del entorno que `_quarto.yml` no puede fijar
(`QUARTO_PYTHON`, el `PATH` para el filtro de shinylive, y el kernel `libro`).

La versión de Quarto está fijada a propósito: la capa interactiva depende de su
runtime de OJS. Actualizarla es un cambio que hay que probar.

Otros comandos:

```bash
make prueba          # pruebas del módulo de datos y de la prosa
make datos           # reconstruye la caché de las 100.000 series de M4
make catalogo        # reconstruye metadatos y catálogo curado
make datos-widgets   # exporta los CSV que los widgets embeben
make referencias     # falla si alguna referencia cruzada quedó sin resolver
make bibliografia    # comprueba referencias.bib contra Crossref (necesita red)
```

## Los datos

```python
from libro.datos import cargar

s = cargar("M3007")                      # una serie por identificador
s = cargar(frecuencia="mensual", n=20)   # un conjunto
s = cargar(dificultad="alta")            # una serie difícil de verdad
s = cargar(fenomeno="quiebre-de-nivel")  # una serie que ilustra un fenómeno
```

Cada serie llega con la partición oficial de M4 ya hecha (`s.entrenamiento`,
`s.prueba`), el horizonte y el período estacional que fija la competencia, la
categoría económica y su índice de complejidad estructural.

Tres niveles de datos, y el libro entero compila con el primero:

1. **En el repositorio**: los metadatos de las 99.935 series (9 MB) y el
   catálogo curado de 33 series con sus valores (126 KB). Sin conexión y sin
   descargas.
2. **Caché local** en `~/.cache/libro-pronostico/`: las 100.000 series en
   parquet (107 MB), opcional, la construye `make datos`.
3. **Descarga** desde el repositorio oficial de M4, una sola vez.

Las series de ejemplo no están elegidas a dedo: se seleccionan con el índice de
complejidad estructural y criterios escritos en código
(`libro/_construir_catalogo.py`), de modo que el catálogo cubra el espectro real
de dificultad y cada serie ilustre un fenómeno distinto.

## Estructura

```
capitulos/     los 25 capítulos
apendices/     soluciones de los ejercicios
laboratorio/   prueba de las tres capas interactivas
libro/         paquete Python: datos, gráficos, scripts de construcción
pruebas/       pruebas automáticas del módulo de datos
estilos/       temas claro y oscuro
```

## Interactividad

Tres niveles, los tres probados y funcionando:

- **Gráficos interactivos** en todo el libro, generados al compilar (Plotly).
- **Celdas editables y ejecutables** en el navegador, con Pyodide vía
  `quarto-live`. Solo en las páginas donde aportan: bajan un intérprete de
  varios megabytes.
- **Widgets con controles**, con shinylive: Shiny para Python compilado a
  WebAssembly, sin servidor.

Lo que corre en el navegador puede usar `numpy`, `pandas`, `scipy`,
`statsmodels`, `scikit-learn`, `xgboost` y `lightgbm`. **No** puede usar
`statsforecast` ni `PyTorch`: no están portados a WebAssembly.

## Reglas del libro

- Todo el código se ejecuta al compilar. Si un capítulo no corre, el libro no se
  publica.
- Datos reales, nunca sintéticos, salvo para ilustrar un punto teórico puntual.
- Cada capítulo cierra con ejercicios; las soluciones van en el apéndice.
- La notación matemática se usa cuando aclara. Si una ecuación se explica mejor
  con tres líneas de código, van las tres líneas.
- Español neutro. Los términos técnicos van en español con el inglés entre
  paréntesis la primera vez.

## Decisiones técnicas

Están en [DECISIONES.md](DECISIONES.md), cada una con su alternativa y el
motivo, incluidos los problemas concretos que hubo que resolver para que la capa
interactiva funcione.

## Estado

- Capítulo 1 escrito y publicado.
- Capítulos 2 a 25: esqueleto con título y alcance.

## Licencia

El libro —texto, figuras y tablas— está bajo
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.es).
El código está bajo licencia MIT. Las series son de la competencia M4 y
conservan las condiciones de sus organizadores. Ver [LICENSE](LICENSE).
