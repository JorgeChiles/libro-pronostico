# Decisiones técnicas

Cada decisión con su alternativa y el motivo. Al final, las que hay que revisar
antes de escribir más capítulos.

Todo lo que dice "probado" acá se probó compilando y abriendo el resultado en un
navegador, no leyendo documentación.

---

## 1 · Quarto para el libro — **confirmado**

Es lo que usa fpp3, ejecuta Python nativamente y produce HTML navegable y PDF
desde la misma fuente. Las alternativas reales eran Jupyter Book y mdBook.
Jupyter Book 2 ya está sobre el mismo motor conceptual pero no tiene el
ecosistema de extensiones que necesitamos —shinylive y quarto-live son
extensiones de Quarto—, y mdBook no ejecuta código.

**Con una salvedad importante que encontré probando**: la capa interactiva
depende del runtime de OJS que Quarto trae adentro. La versión de Quarto no es
un detalle de instalación, es una dependencia del libro. Está fijada en
`1.9.38` —la que tenés instalada y la misma con la que está compilado el sitio
oficial de `quarto-live`— en el `Makefile` y en el flujo de CI. Actualizar
Quarto es un cambio que hay que probar, no aplicar de una.

## 2 · La biblioteca principal de la Parte I — **decidido: reparto statsmodels / statsforecast**

La propuesta inicial era `statsforecast` como biblioteca principal de la Parte I.
Encontré un impedimento duro:

> **`statsforecast` no existe en Pyodide.** Depende de código compilado que no
> está portado a WebAssembly. Tampoco está `PyTorch`.

Lo verifiqué contra el índice de paquetes de las dos distribuciones de Pyodide
que usa el libro. Lo que **sí** está, y por lo tanto puede correr en el
navegador:

| Paquete | shinylive (Pyodide 0.27.7) | quarto-live (Pyodide 0.28.1) |
|---|---|---|
| `numpy`, `pandas`, `scipy` | sí | sí |
| `statsmodels` | 0.14.4 | 0.14.4 |
| `scikit-learn` | 1.6.1 | 1.7.0 |
| `xgboost`, `lightgbm` | sí | sí |
| `matplotlib` | sí | sí |
| `plotly` | 5.23 | **no** (se puede instalar por micropip) |
| `altair` | sí | sí |
| **`statsforecast`** | **no** | **no** |
| **`torch`** | **no** | **no** |

Consecuencia: si `statsforecast` es la biblioteca del cuerpo del texto, **todos
los widgets y todas las celdas editables tienen que reescribirse con
`statsmodels`**. El lector aprendería el concepto con una biblioteca y lo
tocaría con otra, en la misma página. Es el peor de los dos mundos: dobla la
carga cognitiva y dobla el código a mantener.

**El reparto adoptado** (aprobado el 17/08/2026), que es una división de tareas y
no una exclusión:

- **`statsmodels` para enseñar un modelo sobre una serie** (capítulos 4, 6, 8,
  9, 10). Es lo que puede correr en el navegador, así que el código del texto y
  el del widget son el mismo código. Además su API se parece a la notación de
  los libros —`ExponentialSmoothing(trend="add", seasonal="add")`— y permite
  fijar α, β y γ a mano, que es exactamente lo que el widget del capítulo 9
  necesita para enseñar qué hace cada parámetro.
- **`statsforecast` cuando el tema es escala o automatismo**: la selección
  automática de ARIMA en el capítulo 10, la evaluación sobre muchas series del
  capítulo 7, el capítulo 23 de selección de modelos a escala, y toda la Parte
  III. Ahí su ventaja —velocidad y `AutoARIMA` con el algoritmo de
  Hyndman-Khandakar— es el tema del capítulo, no un detalle.

Esto tiene un beneficio secundario que ningún otro texto ofrece: **una tabla de
equivalencias `statsmodels` ↔ `statsforecast` para el mismo modelo**, presentada
donde se introduce la segunda biblioteca. Es información que hoy hay que
reconstruir leyendo dos documentaciones.

Y no compromete la fase 2: la aplicación web usa `statsforecast` en el servidor,
que es donde su velocidad importa. El libro llega ahí igual, solo que declarando
por qué.

## 3 · `scikit-learn` y PyTorch en la Parte II — **confirmado, con un límite**

`scikit-learn` sin objeciones: está en Pyodide, así que los capítulos 14 a 20
pueden tener widgets y celdas editables.

PyTorch para el capítulo 22 sin objeciones **como biblioteca**, pero con una
consecuencia que conviene aceptar de entrada: **el capítulo de aprendizaje
profundo no puede tener celdas ejecutables ni widgets**. No hay PyTorch en
WebAssembly. Ese capítulo va con resultados precomputados y figuras
interactivas generadas al compilar.

No es una pérdida grande. Es justamente el capítulo donde el argumento fuerte
del libro es empírico y viene de tu tesis: en el 68 % de las series el mejor
modelo neuronal cambia solo al cambiar la semilla. Eso se muestra con datos ya
medidos, no ajustando una red en el navegador del lector.

## 4 · Los gráficos: Plotly, con un envoltorio propio — **confirmado con arreglo**

Plotly, y en la Parte II también Altair donde convenga.

Pero hay un problema concreto que encontré y hubo que resolver: Quarto inserta
las figuras de Plotly a través de `requirejs`, y pide el script con una URL sin
extensión (`cdn.plot.ly/plotly-3.7.0.min`) que el CDN responde con **503**. En
una página cualquiera no se nota. En una página que además tiene celdas
editables, el `requirejs` colgado interfiere con el runtime que las monta.

Por eso las figuras del libro se insertan con `libro.graficos.mostrar()`, que
escribe el HTML de la figura, carga `plotly.js` una vez por página con una
etiqueta `<script>` normal y aplica el aspecto común. Efecto lateral bueno:
un solo lugar donde está definida la paleta y la configuración de la barra de
herramientas de todo el libro.

## 5 · GitHub Pages — **confirmado, con un dato de peso**

Compilación automática en cada empujón a `main` y publicación en Pages. El flujo
está en `.github/workflows/publicar.yml` y hace tres cosas antes de publicar:
corre las pruebas del módulo de datos, compila el libro —si un capítulo no
corre, no se publica— e informa el peso del sitio.

El dato de peso, medido: **el sitio compilado pesa 103 MB, de los cuales 99 MB
son los assets de shinylive** (el intérprete de Python compilado a WebAssembly y
sus paquetes). Tres cosas que conviene saber:

- Está muy por debajo del límite de 1 GB de GitHub Pages.
- Es un **costo fijo, no por widget**: los assets se copian una vez para todo el
  sitio. El segundo widget y el séptimo no agregan nada. Así que la regla "usar
  widgets con cuidado" no es por peso del repositorio.
- Lo que sí es por lector es la **descarga en el navegador**, y eso sí depende
  de la página: solo las páginas con widget o con celda editable bajan el
  intérprete. Ahí tu advertencia se sostiene, y la resolvemos poniendo widgets
  solo en los siete capítulos de la lista.

## 6 · El entorno de Python — **decidido**

Entorno virtual propio en `~/.venvs/libro`, **fuera de OneDrive**. Dos razones:
un entorno virtual son decenas de miles de archivos chicos y OneDrive los
sincroniza uno por uno; y el entorno `Maestria2025` de la tesis tiene resultados
validados que no hay que arriesgar instalando cosas nuevas encima.

Python 3.13. Las versiones están fijas en `requisitos.txt`.

**Una restricción heredada**: `statsforecast` todavía exige `pandas < 3`, así que
el libro usa pandas 2.3.3. Conviene saberlo antes de escribir código que use
API de pandas 3.

Compilar pasa siempre por `make libro` y no por `quarto render` a mano, porque
Quarto necesita tres cosas del entorno que `_quarto.yml` no puede fijar:
`QUARTO_PYTHON`, el `PATH` —el filtro de shinylive invoca el ejecutable
`shinylive` por nombre— y el kernel `libro`.

## 7 · Los datos: catálogo en el repositorio, caché afuera — **decidido**

Tres niveles, y el libro entero compila con el primero:

1. **En el repositorio** (9 MB): `metadatos.parquet` con una fila por cada una de
   las 99.935 series —descriptores, índice de complejidad, cuartil de
   dificultad, clúster, entropías, error del naive— y el catálogo curado de 33
   series con sus valores completos (126 KB). Sin conexión y sin descargas.
2. **Caché local** en `~/.cache/libro-pronostico/`: las 100.000 series en
   parquet, 107 MB. La construye `make datos` desde los CSV de la tesis en unos
   minutos. Es opcional: sirve para que el lector se salga del catálogo.
3. **Descarga**, una sola vez, desde el repositorio oficial de M4, si no hay
   nada de lo anterior.

Por qué parquet en formato largo y no los CSV originales: los CSV de M4 vienen
transpuestos —una serie por fila, una columna por observación—, así que sacar una
serie mensual obliga a leer 215 MB. En parquet largo, las seis frecuencias juntas
pesan 107 MB contra 415 MB, y leer una serie cuesta milisegundos.

**99.935 y no 100.000**: son las que tienen descriptores calculados. El pipeline
de la tesis descarta 65 series semanales por ser demasiado cortas.

## 8 · Cómo se eligen las series de ejemplo — **implementado**

Con el índice de complejidad, como pediste, y con criterios escritos en código
(`libro/_construir_catalogo.py`) en vez de a dedo. Para cada fenómeno hay un
filtro sobre los descriptores y un puntaje que ordena qué tan inequívocamente
la serie lo ilustra. Después se completa para que los cuatro cuartiles de
dificultad tengan al menos cinco series.

Resultado: 33 series, 10 fenómenos, las seis frecuencias, los cuatro cuartiles.

    cargar(fenomeno="quiebre-de-nivel")   # M32692, mensual, 318 obs
    cargar(dificultad="alta")             # y sale una difícil de verdad
    cargar(fenomeno="serie-larga")        # D4099, 9.919 observaciones
    cargar(fenomeno="serie-corta")        # Q23425, 16 observaciones

## 9 · La estacionalidad es la de M4, no la natural — **decidido y probado**

M4 declara `Yearly 1 · Quarterly 4 · Monthly 12 · Weekly 1 · Daily 1 ·
Hourly 24`. Es decir, **trata las series semanales y diarias como no
estacionales**, aunque lo natural sería 52 y 7.

El módulo expone las dos: `periodo_estacional` (M4) y `periodo_natural`. Hay una
prueba automática que falla si alguien las confunde, porque es la clase de error
que invalida silenciosamente cualquier comparación con los resultados publicados
de la competencia —está documentado en tu propio
`OBSERVACIONES_PARA_EL_PAPER.md`, sección 5.1— y da además material de primera
para el capítulo 7.

---

## 10 · Dónde vive el repositorio — **resuelto**

En `~/Developer/libro-pronostico`, **fuera de OneDrive**. Un repositorio de Git
sincronizado por OneDrive puede corromperse si dos máquinas escriben el
directorio `.git` a la vez, y `_freeze/` genera muchos archivos chicos que
OneDrive sincroniza de a uno.

OneDrive sigue siendo la casa de los datos de la tesis: el módulo los busca ahí
para construir la caché.

## 11 · Publicación: GitHub Pages, no Squarespace — **decidido**

El libro se publica en **GitHub Pages**, gratis, desde el mismo repositorio y en
cada empujón a `main`. Squarespace no sirve para alojarlo, y conviene tener claro
por qué antes de intentarlo:

- No permite subir un sitio estático arbitrario de cientos de archivos. Está
  pensado para páginas editadas en su propio editor.
- Los widgets necesitan registrar un **service worker en la raíz del dominio**.
  Squarespace no da control sobre eso, así que los widgets no funcionarían.
- El sitio compilado pesa ~104 MB, sobre todo por el intérprete de Python
  compilado a WebAssembly. No es lo que Squarespace espera alojar.

Lo que **sí** se puede hacer, y es lo mejor de los dos mundos: si el dominio está
comprado o administrado en Squarespace, se apunta un subdominio —del estilo
`libro.tudominio.com`— a GitHub Pages con un registro `CNAME` en el panel de DNS.
El libro se sirve desde GitHub con la URL propia. Eso es un cambio de DNS, no una
migración del sitio.

---

## Aprendizaje profundo: sin PyTorch, con resultados precalculados

El capítulo 22 trata redes neuronales y **no entrena ninguna red profunda al
compilar**. La decisión tiene tres partes.

**No se agrega PyTorch a `requisitos.txt`.** Pesa cientos de megabytes con sus
dependencias, alargaría la instalación de CI de un minuto a varios, y sobre todo
**no existe para Pyodide**, así que ninguna celda editable ni ningún widget podría
usarlo. Un capítulo que entrena en la compilación y no en el navegador rompe la
promesa de interactividad del resto del libro.

**Lo que sí se entrena es un perceptrón multicapa con `MLPRegressor` de
`scikit-learn`.** Es una red neuronal completa —capas densas, activaciones,
descenso de gradiente con Adam— y corre tanto al compilar como en el navegador.
Alcanza para mostrar los dos fenómenos que el capítulo necesita: que las redes
necesitan más datos que los árboles, y la varianza por semilla.

**Lo que no se puede entrenar se cita.** Las tablas de la tesis —rangos de
Friedman de 27 modelos sobre 4.773 series, OWA, el OWA horario contra el global, y
el experimento de 90 series × 5 semillas × 5 redes— viajan en el repositorio como
parquet chicos en `libro/datos/tesis/`, se leen con `resultados_tesis()` y se
regeneran con `make tesis` cuando el material de la tesis está a mano. Son
resúmenes agregados, no las 4.773 series.

El capítulo declara la limitación en un recuadro al principio, en vez de mostrar
una LSTM y pedirle al lector que confíe en el número.

**Validación cruzada del enfoque.** El experimento de semillas hecho con el
perceptrón de `scikit-learn` da que el ruido de inicialización supera la brecha
entre arquitecturas en el 68 % de las series: el mismo número que la tesis obtuvo
con cinco arquitecturas distintas, otro conjunto de series y otra biblioteca. Dos
implementaciones sin nada en común coincidiendo es el mejor respaldo que el
capítulo podía tener sin entrenar una LSTM.

---

## Boosting: `scikit-learn` en vez de `xgboost` o `lightgbm`

El capítulo 19 necesita gradient boosting, y en la práctica eso se hace con
`xgboost` o `lightgbm`. El libro usa `HistGradientBoostingRegressor` de
`scikit-learn`, que es la implementación inspirada en LightGBM.

**Por qué.** Son dos dependencias fijas menos en `requisitos.txt`, dos wheels
menos que CI tiene que instalar, y ninguna de las conclusiones del capítulo
depende de la implementación: lo que el capítulo mide es cuánta capacidad
soportan series de cien a trescientas observaciones, y la respuesta —poca— es de
los datos, no del optimizador.

**Qué se pierde.** Velocidad en tablas grandes, y las opciones específicas de
cada biblioteca. Nada de eso importa a esta escala.

**Cuándo revisarlo.** Si la aplicación de fase 2 va a servir boosting en
producción, ahí sí conviene `lightgbm`, y el capítulo lo dice explícitamente en
un recuadro para que nadie lea el libro como una recomendación de biblioteca.

---

## `scikit-learn` en el entorno del navegador

El capítulo 19 tiene una celda editable que ajusta cuatro modelos de
`scikit-learn`, así que hay que agregarlo a `live: packages` en `_quarto.yml`.

**Lo que cuesta.** Pyodide descarga `scikit-learn`, `joblib`, `threadpoolctl` y
`scipy` además de lo que ya bajaba. En una conexión rápida la primera carga de
una página con celda editable pasa de unos 20 segundos a cerca de un minuto. El
navegador lo cachea, así que solo lo paga la primera visita.

**Verificado.** La celda corre en Chrome: ajusta Ridge, kNN, bosque y extra trees
sobre una serie de 102 observaciones y devuelve la tabla de sMAPE y de máximos.

**Nota sobre cómo verificar esto.** Al comprobarlo me equivoqué dos veces
consultando el DOM con el selector `.exercise-editor`, que dio 0 mientras la
celda estaba perfectamente montada y con el cartel «Downloading Pyodide» a la
vista. Es el mismo error que en la primera semana del proyecto. **La verificación
confiable de la capa interactiva es una captura de pantalla**, no una consulta al
DOM: el editor tarda minutos en estar listo y los nombres de clase cambian entre
versiones de quarto-live.

---

## El tiempo de compilación

Con los capítulos 12 a 17 escritos, una compilación en frío pasó de 2,5 a **8
minutos**. El crecimiento no es de Quarto ni del layout: es de los experimentos.
El capítulo 17 ajusta tres estrategias multipaso por dos modelos por 31 series, y
la estrategia directa ajusta `h` modelos cada vez, con `h = 48` en las horarias.
El apéndice suma DirRec, que hace lo mismo otra vez.

Esto **no afecta el trabajo diario**, porque `freeze: auto` sólo re-ejecuta los
capítulos que cambiaron. Lo paga la compilación en frío de CI, y 8 minutos está
lejos de cualquier límite.

Vale tenerlo anotado porque los capítulos que faltan —20 ensambles, 21
bootstrapping, 22 aprendizaje profundo, 23 caso M4— son los más caros de todo el
libro. Si el número se vuelve un problema, hay tres palancas en orden de
preferencia:

1. **Bajar `n_estimators`** en los bosques de los experimentos agregados. De 60 a
   30 no cambia ninguna conclusión y ahorra la mitad.
2. **Precalcular** los experimentos más caros a un `parquet` versionado en el
   repositorio, como ya se hace con `metadatos.parquet`, y que el capítulo sólo
   lea y grafique. Cuesta reproducibilidad a la vista del lector.
3. **Recortar el catálogo** en los experimentos agregados a las series que hacen
   falta para la conclusión, diciéndolo en el pie de la tabla.

Ninguna está aplicada todavía.

---

## Un defecto conocido del catálogo curado

El @sec-los-datos —capítulo 12— documenta que `M16834` tiene sus primeras 435 de
504 observaciones de entrenamiento en el valor 10.000 exacto: es un relleno, no
datos. La serie está en el catálogo como ejemplar del fenómeno *tendencia y
estacionalidad* para la frecuencia mensual, y eso es una mala elección.

**Por qué pasó.** La selección de `libro/_construir_catalogo.py` usa el índice de
complejidad estructural, que resume 29 descriptores por componentes principales.
Ninguno de los 29 pregunta si hay una racha larga de valores idénticos. El índice
midió bien lo que mide: la serie tiene tendencia y estacionalidad en su último
14 %.

**Cuál es la corrección.** Agregar un descriptor de racha máxima —la función
`racha_maxima` del capítulo 12 sirve tal cual— como filtro de exclusión en
`FENOMENOS`, y sumar `M16834` a `SERIES_DEL_LIBRO` para que siga viajando en el
repositorio, porque los capítulos 2, 4 y 12 la usan.

**Por qué no está hecho todavía.** Regenerar el catálogo cambia qué series lo
componen, y con eso los números de las tablas agregadas de los capítulos 5, 13,
15 y 16, que ya están escritos con valores citados en la prosa. La corrección es
correcta y la churn es real; es una decisión de cuándo, no de si.

Mientras no se haga, el defecto está explicado en el capítulo 12 a la vista del
lector, con la medición de cuánto cuesta: Holt-Winters pasa de 2,799 a 7,634 de
sMAPE por entrenar con el relleno, y `naive` no se entera.

---

## Lo que queda por decidir

1. **La versión en PDF.** Está prevista pero no probada. Los widgets y las
   celdas editables no existen en PDF: aparecen como código estático. Hay que
   decidir si en el PDF se reemplazan por una figura equivalente —más trabajo,
   mejor resultado— o si se deja el código a la vista.

2. **El dominio propio.** Si el libro va a vivir en `libro.tudominio.com` en vez
   de en `jorgechiles.github.io/...`, hay que agregar el archivo `CNAME` al
   repositorio y el registro de DNS en Squarespace.
