"""
Almacenamiento de las salidas del pipeline.

Todas las escrituras a disco pasan por este módulo: las fases solo calculan y
devuelven tablas o figuras, y el orquestador decide dónde guardarlas. Así las
tablas comparten la misma codificación y una fase se puede reutilizar sin
generar archivos.
"""

from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure


def guardar_csv(df: pd.DataFrame, ruta: Path) -> None:
    """
    Guarda una tabla en CSV y crea su carpeta si no existe.

    Se usa utf-8-sig porque Excel necesita el BOM para reconocer UTF-8 y, sin
    él, muestra mal las tildes; Power BI y pandas lo leen igual.

    Args:
        df: Tabla a guardar.
        ruta: Ruta del archivo CSV.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, encoding="utf-8-sig")
    print(f"   Exportado: {ruta.parent.name}/{ruta.name} ({len(df):,} filas)")


def guardar_figura(figura: Figure, ruta: Path) -> None:
    """
    Guarda una figura en PNG y crea su carpeta si no existe.

    Args:
        figura: Figura de matplotlib.
        ruta: Ruta del archivo PNG.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(ruta, dpi=150, bbox_inches="tight", facecolor=figura.get_facecolor())
    print(f"   Exportado: {ruta.parent.name}/{ruta.name}")
