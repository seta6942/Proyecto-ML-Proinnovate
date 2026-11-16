"""
Estilo común de los gráficos que genera el pipeline.

Los colores salen de una paleta categórica validada para daltonismo: los dos
primeros tonos se distinguen entre sí con cualquier tipo de visión.
"""

from matplotlib.axes import Axes
from matplotlib.figure import Figure

COLOR_FONDO        = "#fcfcfb"
COLOR_TEXTO        = "#0b0b0b"
COLOR_TEXTO_SUAVE  = "#52514e"
COLOR_REJILLA      = "#e4e3df"
COLOR_SERIE_1      = "#2a78d6"   # azul
COLOR_SERIE_2      = "#eb6834"   # naranja


def crear_figura(ancho: float = 10, alto: float = 6) -> tuple[Figure, Axes]:
    """
    Crea una figura con el fondo, la rejilla y los ejes del estilo común.

    Se instancia Figure directamente y no con pyplot: la figura no queda
    registrada en el estado global de pyplot, no necesita un backend con
    ventana y el recolector de basura libera su memoria al dejar de usarse,
    sin llamar a plt.close.

    Args:
        ancho: Ancho de la figura en pulgadas.
        alto: Alto de la figura en pulgadas.

    Returns:
        La figura y sus ejes.
    """
    figura = Figure(figsize=(ancho, alto), facecolor=COLOR_FONDO)
    ejes = figura.subplots()
    ejes.set_facecolor(COLOR_FONDO)

    # Ejes y rejilla en tonos suaves para que los datos sean lo primero que se lee
    for lado in ["top", "right"]:
        ejes.spines[lado].set_visible(False)
    for lado in ["left", "bottom"]:
        ejes.spines[lado].set_color(COLOR_REJILLA)

    ejes.tick_params(colors=COLOR_TEXTO_SUAVE, labelsize=9)
    ejes.grid(True, color=COLOR_REJILLA, linewidth=0.8)
    ejes.set_axisbelow(True)
    return figura, ejes


def titular(ejes: Axes, titulo: str, subtitulo: str) -> None:
    """
    Escribe el título y un subtítulo explicativo alineados a la izquierda.

    Args:
        ejes: Ejes del gráfico.
        titulo: Título principal.
        subtitulo: Línea que explica cómo leer el gráfico.
    """
    ejes.set_title(subtitulo, loc="left", fontsize=10, color=COLOR_TEXTO_SUAVE, pad=10)
    ejes.figure.suptitle(titulo, x=ejes.get_position().x0, ha="left", fontsize=13, color=COLOR_TEXTO)
