"""Gráficos interactivos del libro.

**Por qué existe `mostrar()` y no se devuelve la figura directamente.**

Quarto inserta las figuras de Plotly usando `requirejs`, y pide el script con
una URL sin extensión (`cdn.plot.ly/plotly-3.7.0.min`) que el CDN responde con
un 503. En una página cualquiera eso pasa desapercibido —Plotly termina
cargando igual—, pero en una página que además tiene celdas editables el
`requirejs` colgado bloquea el runtime de OJS que usa `quarto-live`, y las
celdas nunca se montan.

`mostrar()` evita todo el mecanismo: escribe el HTML de la figura a mano,
carga `plotly.js` una sola vez por página con una etiqueta `<script>` normal y
deja el resto de las figuras sin volver a cargarlo.

Uso:

    from libro.graficos import mostrar, tema

    fig = go.Figure(...)
    mostrar(fig)
"""

from __future__ import annotations

from typing import Any

from IPython.display import HTML, display

# Se carga plotly.js una vez por documento; el resto de las figuras lo reusan.
_ya_cargo_plotly = False

# Configuración de la barra de herramientas, igual en todo el libro.
CONFIG: dict[str, Any] = {
    "displaylogo": False,
    "locale": "es",
    "responsive": True,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}

# Paleta: legible en claro y en oscuro, y distinguible en escala de grises
# para la versión impresa.
COLORES = {
    "observado": "#1f4e79",
    "prueba": "#c0504d",
    "pronostico": "#2e8b57",
    "intervalo": "rgba(46, 139, 87, 0.18)",
    "auxiliar": "#7f7f7f",
}


def tema(fig, *, alto: int = 420, titulo_y: str | None = None):
    """Aplica el aspecto común del libro a una figura de Plotly."""
    fig.update_layout(
        template="plotly_white",
        height=alto,
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.12, x=0, title=None),
        xaxis_title=None,
        yaxis_title=titulo_y,
        font=dict(size=13),
    )
    return fig


def mostrar(fig, *, alto: int | None = None, titulo_y: str | None = None) -> None:
    """Inserta una figura de Plotly sin pasar por el cargador de Quarto."""
    global _ya_cargo_plotly

    if alto is not None or titulo_y is not None:
        tema(fig, alto=alto or 420, titulo_y=titulo_y)

    html = fig.to_html(
        include_plotlyjs="cdn" if not _ya_cargo_plotly else False,
        full_html=False,
        config=CONFIG,
        default_height=f"{fig.layout.height or 420}px",
    )
    _ya_cargo_plotly = True
    display(HTML(html))
