"""
Funciones de limpieza de texto, montos y fechas usadas por el ETL.

Cada función limpia un solo valor y se aplica a la columna con .apply().
"""

import re
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def normalizar_texto(texto: object) -> str | float:
    """
    Quita tildes, comillas y barras sueltas, y deja el texto en mayúsculas.

    Algunos títulos del origen traen restos del escapado de comillas
    (por ejemplo \\MICAELA BASTIDAS\\"), que se reemplazan por espacios.

    Args:
        texto: Valor de una columna de texto.

    Returns:
        El texto normalizado, o NaN si la celda está vacía o no es texto.
    """
    # Las celdas vacías llegan como NaN (float) desde la lectura
    if not isinstance(texto, str):
        return np.nan

    # NFKD separa cada letra de su tilde (Ó -> O + ´) y combining() reconoce
    # esas tildes sueltas para descartarlas
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_tilde = "".join(c for c in nfkd if not unicodedata.combining(c))

    sin_escapes = re.sub(r'[\\"]', " ", sin_tilde)
    texto_limpio = re.sub(r"\s+", " ", sin_escapes).strip().upper()

    # Se devuelve NaN y no una cadena vacía para que pandas y scikit-learn la
    # traten como valor faltante
    return texto_limpio if texto_limpio else np.nan


def limpiar_monto(valor: object) -> float:
    """
    Convierte un monto escrito como texto en distintos formatos a float.

    Admite valores como '135,400.00', 'S/ 135400', '135400,00', '1.234.567'
    y '1.234,56'.

    Args:
        valor: Monto tal como viene en el archivo.

    Returns:
        El monto como float. Los valores vacíos o '-' se consideran 0.0 y el
        texto sin un número reconocible devuelve NaN.
    """
    if pd.isna(valor):
        return 0.0

    texto_original = str(valor).strip()
    if texto_original in ("", "-"):
        return 0.0

    # Quita símbolos de moneda, letras y espacios; quedan dígitos y separadores
    texto = re.sub(r"[^\d.,-]", "", texto_original)

    if not re.search(r"\d", texto):
        return float("nan")

    if "," in texto and "." in texto:
        # El separador que aparece al final es el decimal: '1,234.56' o '1.234,56'
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        # Varias comas solo pueden ser miles ('1,234,567'); una sola, decimal
        if texto.count(",") > 1:
            texto = texto.replace(",", "")
        else:
            texto = texto.replace(",", ".")
    elif texto.count(".") > 1:
        # Varios puntos solo pueden ser separadores de miles: '1.234.567'
        texto = texto.replace(".", "")

    try:
        return float(texto)
    except ValueError:
        return float("nan")


def extraer_fecha_corte_archivo(ruta: Path) -> str:
    """
    Extrae la fecha de corte que aparece en el nombre del archivo.

    Ejemplos:
        'proyectos_ejecucion_20230706.csv'          -> '20230706'
        'Dataset 06 - actualizado al 05012026.csv'  -> '05012026'

    Args:
        ruta: Ruta del archivo de datos.

    Returns:
        La secuencia de 8 dígitos encontrada (o de 6 si no hay de 8), o el
        nombre del archivo si no contiene ninguna.
    """
    nombre = ruta.stem
    coincidencia = re.search(r"\d{8}", nombre) or re.search(r"\d{6}", nombre)
    return coincidencia.group() if coincidencia else nombre


def convertir_fecha(valor: object) -> datetime | None:
    """
    Convierte una fecha numérica a datetime.

    Prueba primero YYYYMMDD (formato de FECHA_CORTE, FECHA_INICIO y FECHA_FIN)
    y luego DDMMYYYY (formato de algunos nombres de archivo, como '05012026').
    Una fecha DDMMYYYY nunca pasa como YYYYMMDD: en la posición del mes
    quedarían los dos primeros dígitos del año (19 o 20), que no son un mes
    válido.

    Args:
        valor: Fecha como texto o número, por ejemplo '20230706' o 20230706.0.

    Returns:
        La fecha como datetime, o None si el valor está vacío o no tiene un
        formato reconocido.
    """
    if pd.isna(valor):
        return None

    # Los valores pueden llegar como '20230706', '20230706.0' o '2023-07-06'
    texto = re.sub(r"[-/]", "", str(valor).strip()).removesuffix(".0")

    for formato in ("%Y%m%d", "%d%m%Y"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue

    return None
