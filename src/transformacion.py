"""
Fase 1b: transformación y estandarización de los cortes.

Depura columnas, convierte fechas y montos, lleva los dólares a soles,
normaliza los textos y deja un registro por contrato.
"""

import numpy as np
import pandas as pd

from src.configuracion import (
    COLS_FINANCIERAS,
    COLS_REQUERIDAS,
    COLS_TEXTO,
    LLAVE_PROYECTO,
    MONEDA_DOLARES,
    MONEDA_SOLES,
    REGION_NO_DETERMINADA,
    TIPO_CAMBIO_ANUAL,
    UMBRAL_NULOS,
    VALORES_REGION_SIN_DATO,
)
from src.limpieza import convertir_fecha, limpiar_monto, normalizar_texto
from src.validacion import validar_columnas, validar_llave_unica

# Duración promedio de un mes (365.25 / 12) para pasar días a meses
DIAS_POR_MES = 30.44


def convertir_columna_fecha(serie: pd.Series) -> pd.Series:
    """
    Aplica convertir_fecha a una columna y la deja con tipo datetime.

    Args:
        serie: Columna de fechas tal como viene en los archivos.

    Returns:
        La columna como datetime. Las fechas vacías, no reconocidas o fuera
        del rango que admite pandas quedan como NaT.
    """
    return pd.to_datetime(serie.apply(convertir_fecha), errors="coerce")


def depurar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Descarta columnas casi vacías o con un único valor.

    Una columna con más de UMBRAL_NULOS de nulos o sin varianza no aporta
    información a los modelos. Las columnas requeridas y las financieras se
    conservan siempre.

    Args:
        df: Cortes concatenados.

    Returns:
        El dataset sin las columnas descartadas.
    """
    protegidas = set(COLS_REQUERIDAS) | set(COLS_FINANCIERAS)
    proporcion_nulos = df.isna().mean()
    valores_unicos = df.nunique(dropna=True)

    descartables = [
        col for col in df.columns
        if col not in protegidas
        and (proporcion_nulos[col] > UMBRAL_NULOS or valores_unicos[col] <= 1)
    ]

    if descartables:
        print(f"   Columnas descartadas por nulos o sin varianza: {descartables}")
    else:
        print("   Ninguna columna supera el umbral de nulos ni es constante.")

    return df.drop(columns=descartables)


def estandarizar_fechas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte las fechas a datetime y calcula la duración de cada proyecto.

    La fecha de corte sale de la columna FECHA_CORTE y, si falta, de la fecha
    que trae el nombre del archivo.

    Args:
        df: Cortes concatenados.

    Returns:
        El dataset con Fecha_Corte, Fecha_Inicio y Fecha_Fin como datetime,
        Anio_Proyecto como entero y la columna Duracion_Meses.
    """
    fecha_archivo = convertir_columna_fecha(df["Fecha_Corte_Archivo"])
    df["Fecha_Corte"] = convertir_columna_fecha(df["Fecha_Corte"]).fillna(fecha_archivo)

    for col in ["Fecha_Inicio", "Fecha_Fin"]:
        if col in df.columns:
            df[col] = convertir_columna_fecha(df[col])
        else:
            df[col] = pd.NaT

    df["Anio_Proyecto"] = pd.to_numeric(df["Anio_Proyecto"], errors="coerce").astype("Int64")

    duracion_dias = (df["Fecha_Fin"] - df["Fecha_Inicio"]).dt.days
    df["Duracion_Meses"] = (duracion_dias / DIAS_POR_MES).round(1)

    # Una fecha de fin anterior a la de inicio es un error de registro: la
    # duración se deja vacía en lugar de usar un valor negativo
    fechas_invertidas = df["Duracion_Meses"] < 0
    if fechas_invertidas.any():
        print(f"   Filas con fecha de fin anterior al inicio: {fechas_invertidas.sum():,}")
        df.loc[fechas_invertidas, "Duracion_Meses"] = np.nan

    return df


def convertir_a_soles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte a soles los montos de los contratos registrados en dólares.

    Usa el tipo de cambio promedio del año del concurso. La moneda original y
    el tipo de cambio aplicado quedan en el dataset para poder auditar la
    conversión.

    Args:
        df: Dataset con las columnas financieras ya numéricas.

    Returns:
        El dataset con todos los montos en soles y las columnas
        Moneda_Original y Tipo_Cambio.
    """
    if "Moneda_Original" not in df.columns:
        df["Moneda_Original"] = MONEDA_SOLES
    df["Moneda_Original"] = df["Moneda_Original"].fillna(MONEDA_SOLES).str.strip().str.upper()

    # Los años fuera de la tabla toman el extremo más cercano (clip), así un
    # concurso de un año sin promedio publicado usa el último valor disponible
    anio_min, anio_max = min(TIPO_CAMBIO_ANUAL), max(TIPO_CAMBIO_ANUAL)
    anios = (
        pd.to_numeric(df["Anio_Proyecto"], errors="coerce")
        .fillna(anio_max)
        .clip(anio_min, anio_max)
        .astype(int)
    )

    es_dolar = df["Moneda_Original"] == MONEDA_DOLARES
    df["Tipo_Cambio"] = anios.map(TIPO_CAMBIO_ANUAL).where(es_dolar, 1.0)

    # Las filas en soles tienen tipo de cambio 1.0 y sus montos no cambian
    for col in COLS_FINANCIERAS:
        df[col] = df[col] * df["Tipo_Cambio"]

    print(f"   Filas convertidas de dólares a soles: {es_dolar.sum():,}")
    return df


def limpiar_montos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte las columnas financieras a float, las lleva a soles y calcula
    el monto total.

    Args:
        df: Cortes concatenados.

    Returns:
        El dataset con montos numéricos en soles y la columna
        Monto_Total_Proyecto.
    """
    for col in COLS_FINANCIERAS:
        if col in df.columns:
            montos = df[col].apply(limpiar_monto)

            sin_reconocer = montos.isna().sum()
            if sin_reconocer:
                print(f"   Aviso: {sin_reconocer:,} montos sin número reconocible en {col}. Se toman como 0.")
            df[col] = montos.fillna(0.0)
        else:
            df[col] = 0.0

    df = convertir_a_soles(df)

    df["Monto_Total_Proyecto"] = (
        df["Monto_Estado"] +
        df["Aporte_Empresa"] +
        df["Aporte_No_Financiero"]
    )
    return df


def normalizar_textos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza las columnas de texto y unifica las regiones sin dato.

    Args:
        df: Cortes concatenados.

    Returns:
        El dataset con los textos normalizados y la columna Region sin
        valores vacíos.
    """
    for col in COLS_TEXTO:
        if col in df.columns:
            df[col] = df[col].apply(normalizar_texto)

    # Los cortes marcan la región faltante de varias formas (vacío, 'N/D').
    # Se agrupan en una sola categoría para que el dashboard las muestre juntas
    # y no se pierdan al filtrar por región.
    region_sin_dato = df["Region"].isna() | df["Region"].isin(VALORES_REGION_SIN_DATO)
    df.loc[region_sin_dato, "Region"] = REGION_NO_DETERMINADA
    print(f"   Filas sin región determinada: {region_sin_dato.sum():,}")

    return df


def deduplicar_contratos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Conserva un solo registro por contrato, priorizando el corte más reciente.

    Cada corte vuelve a publicar los contratos vigentes con su avance, así que
    un contrato aparece en varios archivos. La llave es el contrato y no la
    empresa: una empresa puede tener varios contratos y deduplicar por empresa
    borraría proyectos distintos.

    Se ordena por fecha de corte (O(n log n)) y drop_duplicates conserva la
    primera fila de cada contrato con una tabla hash (O(n)). groupby().first()
    tiene un costo similar, pero toma el primer valor no nulo de cada columna
    por separado: si el último corte traía una celda vacía, la rellenaba con
    la de un corte anterior y mezclaba dos fotos distintas del contrato.

    Args:
        df: Dataset con varios cortes y textos normalizados.

    Returns:
        Un registro por contrato.

    Raises:
        ErrorValidacionDatos: Si el resultado queda vacío o con contratos
            repetidos.
    """
    df[LLAVE_PROYECTO] = df[LLAVE_PROYECTO].str.strip().str.upper().replace("", pd.NA)

    sin_contrato = df[LLAVE_PROYECTO].isna()
    if sin_contrato.any():
        print(f"   Filas descartadas por no tener contrato: {sin_contrato.sum():,}")
        df = df[~sin_contrato]

    # Un mismo contrato puede figurar con otro nombre de empresa en otro corte
    # (abreviaturas, orden de nombres, cambio de razón social). Se informa para
    # dejar a la vista por qué la empresa no sirve como llave.
    nombres_por_contrato = df.groupby(LLAVE_PROYECTO)["Empresa"].nunique()
    print(f"   Contratos con más de un nombre de empresa entre cortes: {(nombres_por_contrato > 1).sum():,}")

    # Orden estable: ante la misma fecha de corte se respeta el orden de lectura
    df_consolidado = (
        df.sort_values("Fecha_Corte", ascending=False, kind="stable", na_position="last")
        .drop_duplicates(subset=LLAVE_PROYECTO, keep="first")
        .reset_index(drop=True)
    )
    validar_llave_unica(df_consolidado, LLAVE_PROYECTO)

    contratos_por_empresa = df_consolidado["Empresa"].value_counts()
    print(
        f"   Empresas con más de un contrato: {(contratos_por_empresa > 1).sum():,} "
        f"(máximo {contratos_por_empresa.max():,} contratos)"
    )
    return df_consolidado


def transformar_datos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ejecuta la transformación completa de los cortes concatenados.

    Args:
        df: Cortes concatenados por la extracción.

    Returns:
        El dataset consolidado, con un registro por contrato.

    Raises:
        ErrorValidacionDatos: Si faltan columnas requeridas o la
            deduplicación deja contratos repetidos.
    """
    validar_columnas(
        df, COLS_REQUERIDAS, "ETL",
        sugerencia="Revisar MAPEO_COLUMNAS en src/configuracion.py.",
    )

    df = depurar_columnas(df)
    df = estandarizar_fechas(df)
    df = limpiar_montos(df)
    df = normalizar_textos(df)
    df = deduplicar_contratos(df)

    print(f"   Contratos únicos: {len(df):,}")
    return df
