"""
Fase 1a: extracción de los cortes históricos de ProInnóvate.

Lee cada archivo (CSV o Excel), homologa sus columnas con MAPEO_COLUMNAS y
concatena los cortes. Un archivo que no se puede leer queda en el registro de
lectura y no detiene la lectura de los demás.
"""

import csv
import zipfile
from pathlib import Path

import pandas as pd

from src.configuracion import ENCODINGS, EXTENSIONES_DATOS, MAPEO_COLUMNAS
from src.limpieza import extraer_fecha_corte_archivo
from src.validacion import ErrorValidacionDatos, detectar_columnas_sin_mapeo

# Errores esperables al leer un archivo dañado o con un formato inesperado.
# UnicodeDecodeError y ParserError heredan de ValueError; BadZipFile aparece
# con un .xlsx corrupto e ImportError cuando falta openpyxl.
ERRORES_LECTURA = (ValueError, OSError, ImportError, zipfile.BadZipFile)


def listar_archivos(dir_datos: Path) -> list[Path]:
    """
    Lista los archivos de datos disponibles en la carpeta indicada.

    Args:
        dir_datos: Carpeta con los cortes históricos.

    Returns:
        Rutas de los archivos ordenadas por nombre.

    Raises:
        FileNotFoundError: Si la carpeta no existe o no contiene archivos de
            datos.
    """
    if not dir_datos.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de datos {dir_datos}.")

    archivos = sorted(
        ruta for ruta in dir_datos.iterdir()
        if ruta.suffix.lower() in EXTENSIONES_DATOS
    )
    if not archivos:
        raise FileNotFoundError(f"La carpeta {dir_datos} no contiene archivos {EXTENSIONES_DATOS}.")

    return archivos


def contar_registros_csv(ruta: Path, encoding: str) -> int:
    """
    Cuenta los registros de un CSV con el lector de la librería estándar, de
    forma independiente a pandas.

    Sirve para comprobar que la lectura no descartó filas en silencio. Vuelve
    a recorrer el archivo (O(n) adicional en tiempo), pero línea por línea, así
    que la memoria adicional es O(1).

    Args:
        ruta: Ruta del archivo CSV.
        encoding: Codificación con la que se leyó el archivo.

    Returns:
        Número de registros sin contar la cabecera.
    """
    with open(ruta, encoding=encoding, newline="") as archivo:
        return sum(1 for _ in csv.reader(archivo, escapechar="\\")) - 1


def leer_csv(ruta: Path) -> tuple[pd.DataFrame, int]:
    """
    Lee un corte histórico en CSV probando varias codificaciones.

    Todas las columnas se leen como texto: así pandas no infiere tipos
    distintos en cada corte y el UBIGEO conserva sus ceros a la izquierda.
    La conversión a números y fechas se hace después, de forma explícita.

    Args:
        ruta: Ruta del archivo CSV.

    Returns:
        El DataFrame leído y el número de registros del archivo según el
        conteo independiente.

    Raises:
        ValueError: Si ninguna codificación de ENCODINGS pudo leer el archivo.
    """
    for encoding in ENCODINGS:
        try:
            # Algunos títulos traen comillas escapadas como \". El motor C con
            # escapechar las interpreta bien, mientras que el motor python con
            # on_bad_lines="skip" descartaba esas filas sin avisar.
            df = pd.read_csv(ruta, encoding=encoding, escapechar="\\", dtype=str)
        except UnicodeDecodeError:
            continue
        except pd.errors.ParserError as error:
            # Respaldo para archivos con filas realmente mal formadas: se omiten
            # esas filas y el registro de lectura deja constancia de cuántas son
            print(f"   {ruta.name} tiene filas mal formadas ({error}). Se omiten.")
            df = pd.read_csv(
                ruta,
                encoding=encoding,
                escapechar="\\",
                dtype=str,
                engine="python",
                on_bad_lines="skip",
            )
        return df, contar_registros_csv(ruta, encoding)

    raise ValueError(f"Ninguna codificación de {ENCODINGS} pudo leer {ruta.name}.")


def leer_archivo(ruta: Path) -> tuple[pd.DataFrame, int]:
    """
    Lee un corte histórico en CSV o Excel según su extensión.

    Args:
        ruta: Ruta del archivo de datos.

    Returns:
        El DataFrame leído y el número de registros esperados. En Excel no hay
        un lector independiente, así que se toman las filas leídas.

    Raises:
        ValueError, OSError, ImportError, zipfile.BadZipFile: Si el archivo no
            se puede leer (ver ERRORES_LECTURA).
    """
    if ruta.suffix.lower() == ".csv":
        return leer_csv(ruta)

    # Igual que en los CSV, todo se lee como texto y se convierte después
    df = pd.read_excel(ruta, dtype=str)
    return df, len(df)


def homologar_columnas(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Lleva los nombres de columna de un corte al esquema canónico.

    Args:
        df: Corte histórico recién leído.

    Returns:
        El corte con las columnas renombradas según MAPEO_COLUMNAS y la lista
        de columnas que el mapeo no reconoce.
    """
    df.columns = df.columns.str.strip().str.upper()
    columnas_sin_mapeo = detectar_columnas_sin_mapeo(df.columns, MAPEO_COLUMNAS)
    return df.rename(columns=MAPEO_COLUMNAS), columnas_sin_mapeo


def extraer_cortes(dir_datos: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Lee todos los cortes de la carpeta y los concatena en un único DataFrame.

    Cada archivo se procesa por separado: si uno falla, el error queda en el
    registro de lectura y se continúa con los demás. Cada fila conserva la
    fecha de corte del nombre de su archivo, que sirve de respaldo si el
    archivo no trae la columna FECHA_CORTE.

    Args:
        dir_datos: Carpeta con los cortes históricos.

    Returns:
        Los cortes concatenados y el registro de lectura, con una fila por
        archivo (estado, filas leídas y esperadas, columnas sin mapeo y
        detalle del error).

    Raises:
        FileNotFoundError: Si la carpeta no existe o no tiene archivos.
        ErrorValidacionDatos: Si no se pudo leer ningún archivo.
    """
    print("\nFASE 1: ETL multi-archivo")

    dataframes = []
    registro = []

    for ruta in listar_archivos(dir_datos):
        try:
            df, filas_esperadas = leer_archivo(ruta)
        except ERRORES_LECTURA as error:
            print(f"   {ruta.name}: no se pudo leer ({error})")
            registro.append({
                "Archivo": ruta.name, "Estado": "ERROR", "Filas_Leidas": 0,
                "Filas_Esperadas": None, "Columnas_Sin_Mapeo": "", "Detalle": str(error),
            })
        else:
            # Se homologa antes de agregar columnas propias para que el paso a
            # mayúsculas no altere sus nombres
            df, columnas_sin_mapeo = homologar_columnas(df)
            df["Fecha_Corte_Archivo"] = extraer_fecha_corte_archivo(ruta)
            dataframes.append(df)

            avisos = []
            if len(df) != filas_esperadas:
                avisos.append(f"{filas_esperadas - len(df):,} filas no leídas")
            if columnas_sin_mapeo:
                avisos.append(f"columnas sin mapeo: {columnas_sin_mapeo}")

            print(f"   {ruta.name}: {len(df):,} filas" + (f" | Aviso: {'; '.join(avisos)}" if avisos else ""))
            registro.append({
                "Archivo": ruta.name, "Estado": "CON AVISOS" if avisos else "OK",
                "Filas_Leidas": len(df), "Filas_Esperadas": filas_esperadas,
                "Columnas_Sin_Mapeo": ", ".join(columnas_sin_mapeo), "Detalle": "; ".join(avisos),
            })

    if not dataframes:
        raise ErrorValidacionDatos("No se pudo leer ninguno de los archivos de datos.")

    df_cortes = pd.concat(dataframes, ignore_index=True, sort=False)
    print(f"   Filas concatenadas: {len(df_cortes):,}")
    return df_cortes, pd.DataFrame(registro)
