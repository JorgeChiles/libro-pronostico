# Compilar el libro siempre igual, acá y en CI.
#
# Quarto necesita tres cosas del entorno y ninguna la resuelve _quarto.yml:
#   - QUARTO_PYTHON: qué Python usa el motor de Jupyter.
#   - PATH: el filtro de shinylive invoca el ejecutable `shinylive` por nombre.
#   - el kernel `libro`: registrado con `make entorno`.
#
# Por eso todo pasa por acá y no por `quarto render` a mano.

VENV ?= $(HOME)/.venvs/libro
PY   := $(VENV)/bin/python
export QUARTO_PYTHON := $(PY)
export PATH := $(VENV)/bin:$(PATH)
# Con esto los capítulos hacen `from libro.datos import cargar` sin tocar
# sys.path: Quarto ejecuta cada capítulo con el directorio del .qmd como cwd.
export PYTHONPATH := $(CURDIR)

.PHONY: ayuda entorno kernel libro html pdf ver limpiar limpiar-todo prueba prueba-sin-conexion referencias datos catalogo datos-widgets tesis bibliografia

ayuda:
	@echo "make entorno   crea el entorno virtual e instala las dependencias"
	@echo "make libro     compila el libro completo (HTML)"
	@echo "make ver       compila y abre el libro en el navegador con recarga"
	@echo "make pdf       compila la versión PDF"
	@echo "make prueba    corre los tests del paquete libro/"
	@echo "make prueba-sin-conexion  compila como en CI: sin caché ni descargas"
	@echo "make referencias  falla si alguna referencia cruzada quedó sin resolver"
	@echo "make bibliografia  comprueba referencias.bib contra Crossref (necesita red)"
	@echo "make datos     reconstruye la caché de M4 desde los CSV originales"
	@echo "make catalogo  reconstruye metadatos y catálogo curado"
	@echo "make datos-widgets  exporta los CSV que embeben los widgets"
	@echo "make limpiar   borra la salida compilada (conserva el freeze)"

entorno:
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip wheel
	$(PY) -m pip install -r requisitos.txt
	$(MAKE) kernel

kernel:
	$(PY) -m ipykernel install --user --name libro --display-name "Python (libro)"

# Quarto avisa de una referencia cruzada sin resolver con un WARN y sigue de
# largo, así que la compilación termina en verde con un enlace roto en el texto.
# Por eso `libro` corre siempre el chequeo al final.
libro html:
	quarto render --to live-html 2>&1 | tee .ultima-compilacion.log
	@$(MAKE) --no-print-directory referencias

# Falla si quedó una referencia cruzada sin resolver. Pasa el registro de la
# última compilación, o vuelve a compilar si no hay ninguno.
referencias:
	@test -f .ultima-compilacion.log || quarto render --to live-html > .ultima-compilacion.log 2>&1
	@if grep -q "Unable to resolve crossref" .ultima-compilacion.log; then \
		echo ""; \
		echo "Referencias cruzadas sin resolver:"; \
		grep "Unable to resolve crossref" .ultima-compilacion.log | sed 's/^/  /'; \
		exit 1; \
	else \
		echo "referencias cruzadas: todas resueltas"; \
	fi

bibliografia:
	$(PY) herramientas/verificar_bibliografia.py

pdf:
	quarto render --to pdf

ver:
	quarto preview

prueba:
	$(PY) -m pytest -q pruebas

# Compila como lo hace la integración continua: sin caché de datos, sin los CSV
# de la tesis a mano y sin permiso para descargar. Si un capítulo pide una serie
# que no viaja en el repositorio, esto falla y ahí hay que verlo, no en CI.
prueba-sin-conexion:
	rm -rf _freeze
	LIBRO_SIN_DESCARGA=1 \
	LIBRO_CACHE=$(CURDIR)/.cache-vacia \
	LIBRO_M4_ORIGEN=$(CURDIR)/.sin-csv \
	quarto render --to live-html 2>&1 | tee .ultima-compilacion.log
	rm -rf .cache-vacia
	@$(MAKE) --no-print-directory referencias

datos:
	$(PY) -m libro._construir_cache

catalogo:
	$(PY) -m libro._construir_catalogo

datos-widgets:
	$(PY) -m libro._datos_widgets

limpiar:
	rm -rf _site

limpiar-todo: limpiar
	rm -rf _freeze .quarto .jupyter_cache

# Trae al repositorio las tablas de resultados de la tesis que cita el capítulo 22.
# Necesita el material de la tesis a mano; una vez generadas, viajan en el repo.
tesis:
	$(PY) -m libro._construir_tesis
