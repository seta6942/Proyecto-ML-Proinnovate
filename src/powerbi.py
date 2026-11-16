"""
Fase 5: modelo estrella para Power BI.

Separa el dataset enriquecido en una tabla de hechos (un proyecto por fila) y
dos dimensiones (región y sector tecnológico). Con esta estructura los filtros
del dashboard se propagan por relaciones uno a muchos y las medidas DAX
trabajan sobre una sola tabla de montos.
"""

import pandas as pd

from src.configuracion import (
    COORDENADAS_DEPARTAMENTOS,
    MACRORREGIONES,
    REGION_NO_DETERMINADA,
    SECTOR_SIN_CLASIFICAR,
    SIN_CLUSTER,
)
from src.validacion import validar_columnas, validar_llaves

COLUMNAS_HECHOS = [
    # Identificación
    "Contrato", "Empresa", "Titulo_Proyecto", "Fondo", "Concurso",
    # Ubicación (Region es la llave hacia Dim_Region)
    "Region", "Provincia", "Distrito", "Ubigeo", "Ambito",
    # Tiempo
    "Anio_Proyecto", "Fecha_Inicio", "Fecha_Fin", "Fecha_Corte", "Duracion_Meses",
    # Montos en soles
    "Moneda_Original", "Tipo_Cambio", "Monto_Estado", "Aporte_Empresa",
    "Aporte_No_Financiero", "Aporte_Privado_Total", "Monto_Total_Proyecto",
    # Métricas por proyecto
    "Ratio_Apalancamiento_Privado", "Ratio_Apalancamiento_Monetario", "Porcentaje_Aporte_Estado",
    # Resultados de Machine Learning (Cluster_Innovacion es la llave hacia Dim_Sector)
    "Cluster_Innovacion", "Es_Anomalia", "Puntaje_Anomalia", "Motivo_Anomalia",
    "Desviacion_Monto_Concurso", "Aporte_Privado_Estimado", "Brecha_Aporte_Privado",
]


def construir_dim_region() -> pd.DataFrame:
    """
    Construye la dimensión de regiones con su macrorregión y coordenadas.

    Returns:
        Una fila por departamento más la fila de región no determinada.
    """
    filas = [
        {
            "Region": region,
            "Macrorregion": macrorregion,
            "Latitud": COORDENADAS_DEPARTAMENTOS[region][0],
            "Longitud": COORDENADAS_DEPARTAMENTOS[region][1],
        }
        for macrorregion, regiones in MACRORREGIONES.items()
        for region in regiones
    ]

    # Sin coordenadas para que el mapa no la ubique en ningún punto del país
    filas.append({
        "Region": REGION_NO_DETERMINADA,
        "Macrorregion": REGION_NO_DETERMINADA,
        "Latitud": None,
        "Longitud": None,
    })
    return pd.DataFrame(filas).sort_values("Region").reset_index(drop=True)


def construir_dim_sector(resumen_clusters: pd.DataFrame) -> pd.DataFrame:
    """
    Construye la dimensión de clústeres y sectores tecnológicos.

    Args:
        resumen_clusters: Resumen de la Fase 2, una fila por clúster.

    Returns:
        Una fila por clúster más la de los títulos sin clasificar.
    """
    dim_sector = resumen_clusters[
        ["Cluster_Innovacion", "Sector_Tecnologico", "Cluster_Terminos", "Terminos_Principales"]
    ]

    sin_clasificar = pd.DataFrame([{
        "Cluster_Innovacion": SIN_CLUSTER,
        "Sector_Tecnologico": SECTOR_SIN_CLASIFICAR,
        "Cluster_Terminos": SECTOR_SIN_CLASIFICAR,
        "Terminos_Principales": "Título sin contenido suficiente para clasificar",
    }])
    return pd.concat([dim_sector, sin_clasificar], ignore_index=True)


def construir_modelo_estrella(
    df: pd.DataFrame,
    resumen_clusters: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """
    Ejecuta la Fase 5 y arma las tablas del modelo estrella.

    Args:
        df: Dataset enriquecido con todas las fases.
        resumen_clusters: Resumen de clústeres de la Fase 2.

    Returns:
        Las tablas del modelo, con el nombre de archivo como llave.

    Raises:
        ErrorValidacionDatos: Si faltan columnas de la tabla de hechos o hay
            llaves sin fila en su dimensión.
    """
    print("\nFASE 5: modelo estrella para Power BI")
    validar_columnas(df, COLUMNAS_HECHOS, "Power BI")

    hechos = df[COLUMNAS_HECHOS].copy()

    # Fechas en formato ISO para que Power BI las reconozca sin depender de la
    # configuración regional del equipo
    for col in ["Fecha_Inicio", "Fecha_Fin", "Fecha_Corte"]:
        hechos[col] = hechos[col].dt.strftime("%Y-%m-%d")

    dim_region = construir_dim_region()
    dim_sector = construir_dim_sector(resumen_clusters)

    validar_llaves(hechos, dim_region, "Region")
    validar_llaves(hechos, dim_sector, "Cluster_Innovacion")

    return {
        "Proyectos.csv": hechos,
        "Dim_Region.csv": dim_region,
        "Dim_Sector.csv": dim_sector,
    }
