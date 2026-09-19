"""
PORTAFOLIO PROINNOVATE - PIPELINE COMPLETO
Autor: Sandro Estanislao Tapia Acosta
Última actualización: 19/09/2026

Datasets: 6 cortes históricos del programa ProInnóvate (Perú)
"""

import warnings
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore")

DIR_DATOS   = Path("Data")
DIR_SALIDAS = Path("Outputs")
DIR_SALIDAS.mkdir(parents=True, exist_ok=True)

# Archivo de salida de la Fase 1
CSV_CONSOLIDADO = DIR_SALIDAS / "dataset_consolidado_limpio.csv"

# Fase 1: ETL Multi-archivo y Limpieza

MAPEO_COLUMNAS = {
    "CONTRATO"           : "Contrato",
    "CODIGO"             : "Contrato",
    "NOMBRE_SOLICITANTE" : "Empresa",
    "EMPRESA"            : "Empresa",
    "RAZON_SOCIAL"       : "Empresa",
    "TITULO"             : "Titulo_Proyecto",
    "TITULO_PROYECTO"    : "Titulo_Proyecto",
    "FONDO"              : "Sector",
    "SECTOR"             : "Sector",
    "DEPARTAMENTO"       : "Region",
    "REGION"             : "Region",
    "DPTO"               : "Region",
    "MONTO_RNR"          : "Monto_Estado",
    "MONTO_PROINNOVATE"  : "Monto_Estado",
    "MONTO_ESTADO"       : "Monto_Estado",
    "MONTO_FINANCIERO"   : "Aporte_Empresa",
    "APORTE_EMPRESA"     : "Aporte_Empresa",
    "FECHA_CORTE"        : "Fecha_Corte",
    "ANIO"               : "Anio_Proyecto",
    "CONCURSO"           : "Concurso",
    "FECHA_INICIO"       : "Fecha_Inicio",
    "FECHA_FIN"          : "Fecha_Fin",
    "MONTO_NO_FINANCIERO": "Aporte_No_Financiero",
    "UBIGEO"             : "Ubigeo",
    "PROVINCIA"          : "Provincia",
    "DISTRITO"           : "Distrito",
    "MONEDA"             : "Moneda",
}

COLS_REQUERIDAS = [
    "Contrato", "Empresa", "Titulo_Proyecto", "Sector", "Region",
    "Monto_Estado", "Aporte_Empresa", "Fecha_Corte"
]