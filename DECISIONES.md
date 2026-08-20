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

## El defecto del catálogo curado, corregido

El @sec-los-datos —capítulo 12— documenta que `M16834` tiene 435 de sus 504
observaciones de entrenamiento en el valor 10.000 exacto: es un relleno, no
datos. La serie estaba en el catálogo como ejemplar de *tendencia y
estacionalidad* para la frecuencia mensual, y eso era una mala elección.

**Por qué pasó.** La selección de `libro/_construir_catalogo.py` usa el índice
de complejidad estructural, que resume 29 descriptores por componentes
principales. Ninguno de los 29 pregunta si hay una racha larga de valores
idénticos. El índice midió bien lo que mide: la serie tiene tendencia y
estacionalidad en su último 14 %.

**Qué se hizo.** Se agregó `racha_maxima` como descriptor número 30 —viaja en
`metadatos.parquet` para las 99.935 series— y se usa como filtro de exclusión:
ninguna serie con una racha mayor al 20 % de su largo puede representar un
fenómeno. El umbral sale de la distribución medida sobre las 100.000 series: la
mediana tiene una racha del 1,5 % de su largo, el percentil 99 llega al 11 %, el
máximo al 92 %, y el corte en 20 % excluye 257 series, el 0,26 %. Ninguna
frecuencia pierde más del 0,54 % de las suyas. `M16834` da 86 %.

`M16834` sigue viajando porque los capítulos 2, 4 y 12 la nombran, con la
etiqueta `usada-en-el-texto`. Su cupo lo tomó `Q23601`, trimestral, 699
observaciones, racha máxima de dos.

**El segundo defecto, que apareció al arreglar el primero.** La primera
regeneración cambió cinco series en vez de una. La causa no era el filtro: la
curación ordenaba las candidatas con `sort_values` sin especificar el algoritmo,
y el `quicksort` de pandas no es estable. En fenómenos con cientos de empatados
—hay cientos de series anuales con exactamente 13 observaciones— el desempate lo
decidía el orden accidental de las filas, así que el catálogo no era reproducible
ante ningún cambio de entrada. Con el desempate explícito por identificador y
`kind="stable"`, regenerar dos veces da el mismo catálogo y el cambio quedó
acotado a lo que tenía que ser.

**El mecanismo de fijar series también cambió.** `SERIES_DEL_LIBRO` pasó de
`id → motivo` a `id → (etiqueta, motivo)`: una serie fijada conserva la etiqueta
del fenómeno que ilustra y consume uno de sus cupos, en vez de sumarse aparte
como `usada-en-el-texto`. Sin eso, fijar las cinco series que los capítulos 13,
15 y 16 nombran por identificador les habría cambiado la etiqueta y habría
desplazado al resto del catálogo. Dos pruebas nuevas lo fijan: que la etiqueta
declarada sea la del catálogo, y que ningún ejemplar supere el umbral de racha.

**Dos agujeros en las defensas, encontrados al hacer el cambio.** Los dos daban
compilación en verde con el libro mal, que es la peor combinación posible.

1. `freeze: auto` mira la fecha del `.qmd`, no la de los parquet. Después de
   regenerar el catálogo, los capítulos que no se editaron siguieron publicando
   los números del catálogo anterior. Ahora `make catalogo` borra `_freeze`.
2. `quarto render ... | tee` devuelve el estado de salida de `tee`, así que
   `make libro` terminaba en 0 aunque el render abortara a la mitad. Se agregó
   `set -o pipefail` y `SHELL := /bin/bash`. El error que lo destapó fue mío
   —una variable de capítulo pisada al reescribir prosa— y se publicó en verde.

Para encontrar qué prosa quedó desactualizada se comparó el `_freeze` versionado
en git contra el nuevo: los números que dejaron de aparecer en alguna salida y
todavía estaban escritos en el texto. Dieron 128 en siete documentos, y esa lista
es exacta, no una búsqueda a ojo.

**Lo que costó.** El catálogo pasó de 34 a 35 series, así que todos los agregados
que se calculan sobre él se movieron. Los capítulos que los citaban en prosa
pasaron a calcularlos en línea, que era la manera de que no vuelva a pasar. Tres
conclusiones cambiaron de signo y se reescribieron: la elastic net del capítulo 18
ya no le gana a no regularizar, el error de Ridge en el ejercicio 6 del capítulo 19
deja de crecer con el horizonte, y el ejercicio 3 del capítulo 22 pasa de
contradecir a la tesis a reproducirla.

---

## Las tres defensas de la aplicación, ahora medidas

El capítulo 25 mide las tres decisiones de la fase 2 que estaban tomadas sin
número. Los resultados están sobre 34 series y 641 pasos del catálogo, y quedan
acá porque son decisiones de producto, no solo de libro.

**La cota de cordura es condicional a la tendencia, no fija.** Recortar el
pronóstico al rango observado del histórico mejora el MASE medio de 36,7 a 16,2 y
el peor caso de 356 a 116, pero daña las series con tendencia limpia —hasta 5,7
puntos de sMAPE en una— porque su futuro está legítimamente arriba del máximo
histórico. La regla que se queda deja espacio proporcional a la pendiente cuando
la fuerza de la tendencia pasa de 0,8: mismo beneficio, peor daño de 0,7 puntos.
El barrido del umbral está en las soluciones del capítulo y muestra que la regla
no necesita calibración fina.

**Al punto, cota estadística; al intervalo, solo cota física.** Es asimétrico y
no era obvio. Sobre el pronóstico puntual la cota apretada gana. Sobre el
intervalo del 95 % por bootstrap, acotarlo al rango observado cuesta 9,5 puntos
de cobertura, sobre una cobertura que ya era del 81 % en vez del 95 %. Un piso en
cero, en cambio, no cuesta nada: la cobertura queda idéntica y el intervalo se
angosta un 23 %, porque el 23 % de su ancho estaba debajo de cero en series
estrictamente positivas.

**Tres a cinco semillas con la mediana.** Con el perceptrón que sí se puede
entrenar en el navegador, la dispersión entre la mejor y la peor semilla es del
54 % en la serie mediana. La mediana de cinco le gana a fijar `random_state=0` en
21 de 31 series, no alcanza a la mejor semilla —que es un oráculo— y sobre todo
evita caer en la peor. Cuesta 4,6 veces el tiempo de una sola y es paralelizable.

---

## El costo de `sample_entropy` era de implementación, no de algoritmo

El capítulo 23 dejó dicho que el índice de complejidad, para calcularse en línea,
había que vectorizarlo o precomputarlo. El capítulo 25 lo midió: **vectorizar el
bucle interno alcanza.** La misma cuenta, con el mismo resultado hasta el último
decimal, pasa de 4.095 ms a 104 ms en una serie de 2.794 puntos —un factor 39 que
crece con la longitud— y las 16,6 horas del pipeline de la tesis caen al mismo
ritmo.

Lo que la vectorización no arregla es la complejidad $O(n^2)$: en la serie de
9.919 puntos del catálogo la versión rápida todavía tarda 1,2 segundos. Para eso
sigue haciendo falta el tope de 4.000 puntos que usó la tesis, que deja cualquier
serie en unos 200 ms.

Para la aplicación hay una salida mejor: el capítulo 24 midió que el clasificador
que elige método **no pierde nada** al quedarse sin `sample_entropy`. Se calcula
después de responder, o no se calcula.

---

## Lo que queda por decidir

1. **La versión en PDF.** Está prevista pero no probada. Los widgets y las
   celdas editables no existen en PDF: aparecen como código estático. Hay que
   decidir si en el PDF se reemplazan por una figura equivalente —más trabajo,
   mejor resultado— o si se deja el código a la vista.

2. **El dominio propio.** Elegido: `pronosticos.dev`. Falta comprarlo y hacer
   los cuatro pasos de abajo, en ese orden. Si se hace al revés —el `CNAME` en
   el repositorio antes del DNS— GitHub deja de servir en `github.io` y el libro
   queda inaccesible hasta que el DNS resuelva.

   **Por qué `.dev` y no `.com`.** El plural «pronosticos» está tomado en `.com`,
   `.org`, `.net`, `.app` y `.io`, todos en manos de revendedores: es la palabra
   clave de las apuestas deportivas en español. `.dev` esquiva esa competencia,
   obliga HTTPS por diseño —está en la lista HSTS precargada— y se lee como
   material técnico.

   **Los cuatro pasos.**

   1. Comprar el dominio. En el registrador se confirma la disponibilidad real;
      el whois de `.dev` no responde desde una terminal cualquiera.
   2. En el DNS del registrador, para el dominio raíz, cuatro registros `A` a las
      direcciones de GitHub Pages —confirmarlas en la documentación de GitHub al
      momento de hacerlo, porque cambian—: `185.199.108.153`, `185.199.109.153`,
      `185.199.110.153`, `185.199.111.153`. Y un `CNAME` de `www` a
      `jorgechiles.github.io`. Si el registrador soporta `ALIAS`/`ANAME`, uno solo
      a `jorgechiles.github.io` reemplaza a los cuatro `A`.
   3. `gh api -X PUT repos/JorgeChiles/libro-pronostico/pages -f cname=pronosticos.dev`
      y después, en el repositorio, un archivo `CNAME` en la raíz con el dominio
      —Quarto lo copia a `_site/` si está en `resources`, o el workflow lo agrega—.
   4. Esperar el certificado y activar «Enforce HTTPS». Verificar los dos:
      `curl -I https://pronosticos.dev` y que una celda editable ejecute, porque
      el service worker de los widgets se registra por dominio y es lo primero
      que se rompe al mudar el sitio.

   **Lo que hay que revisar después de mudarlo.** El `site-url` de `_quarto.yml`
   —lo usan los enlaces canónicos y el buscador— y que el service worker de
   shinylive quede en la raíz del dominio nuevo.

3. **Lo que era el punto 2.** Si el libro va a vivir en `libro.tudominio.com` en vez
   de en `jorgechiles.github.io/...`, hay que agregar el archivo `CNAME` al
   repositorio y el registro de DNS en Squarespace.
