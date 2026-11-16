"""
Métricas financieras y territoriales.

Calcula cuánto capital privado atrae cada sol del Estado (Ratio de
Apalancamiento Privado) y ubica cada proyecto en su ámbito y macrorregión para
medir la descentralización de los fondos.
"""

import numpy as np
import pandas as pd

from src.configuracion import (
    AMBITO_LIMA,
    AMBITO_REGIONES,
    MACRORREGIONES,
    REGION_NO_DETERMINADA,
)
from src.validacion import validar_columnas

COLUMNAS_ENTRADA = [
    "Contrato", "Region", "Provincia", "Monto_Estado", "Aporte_Empresa",
    "Aporte_No_Financiero", "Monto_Total_Proyecto",
]


def calcular_metricas_financieras(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega el aporte privado total y los ratios de apalancamiento.

    - Aporte_Privado_Total: aporte monetario más aporte no monetario de la
      empresa.
    - Ratio_Apalancamiento_Privado: soles privados por cada sol del Estado.
      Un valor de 0.5 indica que la empresa pone S/ 0.50 por cada S/ 1.00
      del subsidio.
    - Ratio_Apalancamiento_Monetario: igual, pero solo con dinero en
      efectivo. El aporte no monetario (horas, equipos) lo valoriza la propia
      empresa, por eso conviene verlo por separado.
    - Porcentaje_Aporte_Estado: parte del costo total que cubre el subsidio.

    Args:
        df: Dataset consolidado con montos en soles.

    Returns:
        El dataset con las cuatro columnas nuevas.
    """
    df["Aporte_Privado_Total"] = df["Aporte_Empresa"] + df["Aporte_No_Financiero"]

    # Un proyecto sin monto del Estado no tiene ratio definido: se deja NaN en
    # lugar de infinito para que no distorsione promedios ni gráficos
    monto_estado = df["Monto_Estado"].replace(0, np.nan)
    df["Ratio_Apalancamiento_Privado"]   = (df["Aporte_Privado_Total"] / monto_estado).round(4)
    df["Ratio_Apalancamiento_Monetario"] = (df["Aporte_Empresa"] / monto_estado).round(4)

    monto_total = df["Monto_Total_Proyecto"].replace(0, np.nan)
    df["Porcentaje_Aporte_Estado"] = (df["Monto_Estado"] / monto_total).round(4)

    return df


def asignar_ambito_territorial(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clasifica cada proyecto por macrorregión y por ámbito (Lima o regiones).

    La provincia de Lima y el Callao forman Lima Metropolitana. Las demás
    provincias del departamento de Lima (Huaura, Cañete, etc.) cuentan como
    regiones, porque el objetivo es medir cuánto sale de la capital.

    Args:
        df: Dataset consolidado con Region y Provincia normalizadas.

    Returns:
        El dataset con las columnas Macrorregion y Ambito.
    """
    # Diccionario invertido región -> macrorregión: map lo resuelve en O(n)
    # con búsquedas O(1), sin recorrer las listas de MACRORREGIONES por fila
    region_a_macrorregion = {
        region: macrorregion
        for macrorregion, regiones in MACRORREGIONES.items()
        for region in regiones
    }
    df["Macrorregion"] = df["Region"].map(region_a_macrorregion).fillna(REGION_NO_DETERMINADA)

    es_lima_metropolitana = (
        ((df["Region"] == "LIMA") & (df["Provincia"] == "LIMA")) |
        (df["Region"] == "CALLAO")
    )

    df["Ambito"] = np.select(
        [df["Region"] == REGION_NO_DETERMINADA, es_lima_metropolitana],
        [REGION_NO_DETERMINADA, AMBITO_LIMA],
        default=AMBITO_REGIONES,
    )
    return df


def resumir_por_region(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resume proyectos, montos y apalancamiento por región.

    El ratio de cada región se calcula como suma de aportes privados entre
    suma de montos del Estado (ratio de sumas). Promediar los ratios de cada
    proyecto daría el mismo peso a un proyecto de S/ 15 mil que a uno de
    S/ 15 millones.

    Args:
        df: Dataset con las métricas financieras y territoriales.

    Returns:
        Una fila por región, ordenada por monto del Estado.
    """
    resumen = (
        df.groupby(["Region", "Macrorregion"], as_index=False)
        .agg(
            N_Proyectos=("Contrato", "count"),
            Monto_Estado=("Monto_Estado", "sum"),
            Aporte_Privado=("Aporte_Privado_Total", "sum"),
        )
    )
    resumen["Ratio_Apalancamiento_Privado"] = (
        resumen["Aporte_Privado"] / resumen["Monto_Estado"].replace(0, np.nan)
    ).round(4)
    resumen["Participacion_Monto_Estado"] = (
        resumen["Monto_Estado"] / resumen["Monto_Estado"].sum()
    ).round(4)

    return resumen.sort_values("Monto_Estado", ascending=False).reset_index(drop=True)


def imprimir_resumen_general(df: pd.DataFrame) -> None:
    """
    Muestra los indicadores globales de inversión y descentralización.

    Args:
        df: Dataset con las métricas financieras y territoriales.
    """
    total_estado  = df["Monto_Estado"].sum()
    total_privado = df["Aporte_Privado_Total"].sum()

    # El porcentaje se calcula sobre los proyectos con región conocida: los que
    # no la tienen no son ni de Lima ni de regiones
    con_region = df["Ambito"] != REGION_NO_DETERMINADA
    monto_con_region = df.loc[con_region, "Monto_Estado"].sum()
    monto_regiones = df.loc[df["Ambito"] == AMBITO_REGIONES, "Monto_Estado"].sum()

    print(f"   Inversión del Estado        : S/ {total_estado:,.0f}")
    print(f"   Aporte privado total        : S/ {total_privado:,.0f}")
    print(f"   Ratio de apalancamiento     : {total_privado / total_estado:.2f}")
    print(f"   Fondos fuera de Lima/Callao : {monto_regiones / monto_con_region:.1%}")


def ejecutar_metricas(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calcula las métricas financieras y territoriales.

    Args:
        df: Dataset consolidado de la Fase 1.

    Returns:
        El dataset con las métricas agregadas y el resumen por región.

    Raises:
        ErrorValidacionDatos: Si el dataset no trae las columnas del ETL.
    """
    print("\nMÉTRICAS: apalancamiento privado y descentralización")
    validar_columnas(df, COLUMNAS_ENTRADA, "Métricas")

    df = calcular_metricas_financieras(df)
    df = asignar_ambito_territorial(df)
    imprimir_resumen_general(df)

    return df, resumir_por_region(df)
