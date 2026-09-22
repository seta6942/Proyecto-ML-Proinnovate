"""
PORTAFOLIO PROINNOVATE - PIPELINE COMPLETO
Autor: Sandro Estanislao Tapia Acosta
Última actualización: 19/09/2026

Datasets: 6 cortes históricos del programa ProInnóvate (Perú)
"""

import warnings
import pandas as pd
from pathlib import Path
import re
import unicodedata
import glob

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

#Funciones para limpieza de datos

def quitar_tildes(texto):
    if pd.isna(texto) or type(texto) != str:
        return texto
    
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_tilde = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tilde.upper().strip()


def limpiar_monto(valor):
    if pd.isna(valor):
        return 0.0
    
    texto = str(valor).strip()
    texto = re.sub(r"[S$/€£¥₹\s]", "", texto)
    
    if "," in texto and "." in texto:
        texto = texto.replace(",", "")
    elif "," in texto and "." not in texto:
        texto = texto.replace(",", ".")
        
    texto = re.sub(r"[^\d.]", "", texto)
    return float(texto) if texto else 0.0


def extraer_fecha_corte_archivo(filepath):
    nombre = Path(filepath).stem
    
    match_8 = re.search(r"(\d{8})", nombre)
    if match_8:
        return match_8.group(1)
        
    match_6 = re.search(r"(\d{6})", nombre)
    if match_6:
        return match_6.group(1)
        
    return nombre


def normalizar_fecha(fecha_str):
    if pd.isna(fecha_str):
        return "9999-12-31" 
    
    s = str(fecha_str).replace("-", "").replace("/", "").strip()
    
    # a veces pandas lee '20211231' como 20211231.0
    if s.endswith(".0"):
        s = s[:-2]
        
    if len(s) == 8:
        try:
            return pd.to_datetime(s, format="%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
        
        try:
            return pd.to_datetime(s, format="%d%m%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
            
    return s

#Lectura y concatenación de CSVs

archivos = sorted(glob.glob(str(DIR_DATOS / "*.csv")))
assert len(archivos) > 0, f"Carpeta {DIR_DATOS} vacía. Saliendo."

dataframes = []

for filepath in archivos:
    df = None
    
    for enc in ["utf-8", "utf-8-sig", "latin-1"]:
        try:
            df = pd.read_csv(
                filepath,
                encoding=enc,
                on_bad_lines="skip",
                engine="python",
                quotechar='"',
                escapechar='\\'
            )
            break
        except Exception:
            continue
            
    if df is None:
        print(f"-> Archivo corrupto o no se pudo leer: {filepath}")
        continue

    df["Anio_Corte_Archivo"] = extraer_fecha_corte_archivo(filepath)
    
    df.columns = df.columns.str.strip().str.upper()
    df.rename(columns=MAPEO_COLUMNAS, inplace=True)
    
    dataframes.append(df)

df_all = pd.concat(dataframes, ignore_index=True, sort=False)

#Transformación y Estandarización

if "Fecha_Corte" in df_all.columns:
    df_all["Fecha_Corte_Std"] = df_all["Fecha_Corte"].apply(normalizar_fecha)
else:
    df_all["Fecha_Corte_Std"] = df_all["Anio_Corte_Archivo"].apply(
        lambda x: normalizar_fecha(x) if len(str(x)) >= 6 else str(x)
    )

df_all["Anio_Corte_Num"] = (
    df_all["Fecha_Corte_Std"]
    .str.replace("-", "")
    .str[:8]
    .apply(lambda x: int(x) if str(x).isdigit() else 0)
)

cols_financieras = ["Monto_Estado", "Aporte_Empresa", "Aporte_No_Financiero"]
for col in cols_financieras:
    if col in df_all.columns:
        df_all[col] = df_all[col].apply(limpiar_monto)
    else:
        df_all[col] = 0.0

df_all["Monto_Total_Proyecto"] = (
    df_all["Monto_Estado"] +
    df_all["Aporte_Empresa"] +
    df_all["Aporte_No_Financiero"]
)

cols_texto = ["Region", "Sector", "Empresa", "Titulo_Proyecto"]
for col in cols_texto:
    if col in df_all.columns:
        df_all[col] = df_all[col].apply(quitar_tildes)