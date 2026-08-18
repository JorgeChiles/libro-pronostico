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

.PHONY: ayuda entorno kernel libro html pdf ver limpiar limpiar-todo prueba datos

ayuda:
	@echo "make entorno   crea el entorno virtual e instala las dependencias"
	@echo "make libro     compila el libro completo (HTML)"
	@echo "make ver       compila y abre el libro en el navegador con recarga"
	@echo "make pdf       compila la versión PDF"
	@echo "make prueba    corre los tests del paquete libro/"
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

libro html:
	quarto render --to live-html

pdf:
	quarto render --to pdf

ver:
	quarto preview

prueba:
	$(PY) -m pytest -q pruebas

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
