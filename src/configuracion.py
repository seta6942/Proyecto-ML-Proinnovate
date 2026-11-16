"""
Configuración global del pipeline.

Centraliza rutas, diccionarios de mapeo y parámetros de cada fase para que los
módulos no repitan valores escritos a mano.
"""

from pathlib import Path

# ==============================================================================
# Rutas y parámetros generales
# ==============================================================================

# Las rutas se resuelven desde la raíz del repositorio y no desde la carpeta de
# ejecución, así el pipeline funciona aunque se lance desde otro directorio.
DIR_RAIZ    = Path(__file__).resolve().parent.parent
DIR_DATOS   = DIR_RAIZ / "Data"
DIR_SALIDAS = DIR_RAIZ / "Outputs"

# Dataset con todas las columnas que agregan las fases del pipeline
CSV_ENRIQUECIDO = DIR_SALIDAS / "dataset_final_enriquecido.csv"

SEMILLA = 42

# ==============================================================================
# Fase 1: ETL multi-archivo
# ==============================================================================

CSV_CONSOLIDADO      = DIR_SALIDAS / "dataset_consolidado_limpio.csv"
CSV_REGISTRO_LECTURA = DIR_SALIDAS / "registro_lectura.csv"

# Algunos cortes se publican como hojas de cálculo; el ETL acepta ambos formatos
EXTENSIONES_DATOS = (".csv", ".xlsx")

# utf-8-sig lee igual que utf-8 pero además descarta el BOM. Con utf-8 a secas,
# un archivo con BOM dejaría la primera columna como '﻿FONDO' y el mapeo
# no la reconocería. latin-1 queda como respaldo porque nunca falla al decodificar.
ENCODINGS = ["utf-8-sig", "latin-1"]

# Los cortes de distintos años pueden nombrar la misma columna de otra forma
# (schema drift). Cada variante apunta al nombre canónico que usa el resto del
# pipeline, de modo que un corte con RAZON_SOCIAL o CODIGO se integra sin
# cambiar el código. Las columnas que no figuran aquí se reportan al leer.
MAPEO_COLUMNAS = {
    "CONTRATO"           : "Contrato",
    "CODIGO"             : "Contrato",
    "NOMBRE_SOLICITANTE" : "Empresa",
    "EMPRESA"            : "Empresa",
    "RAZON_SOCIAL"       : "Empresa",
    "TITULO"             : "Titulo_Proyecto",
    "TITULO_PROYECTO"    : "Titulo_Proyecto",
    # FONDO es el programa que financia el contrato (FINCYT, FIDECOM, BID 4...),
    # no el sector económico. El sector tecnológico se obtiene en la Fase 2.
    "FONDO"              : "Fondo",
    "SECTOR"             : "Fondo",
    "DEPARTAMENTO"       : "Region",
    "REGION"             : "Region",
    "DPTO"               : "Region",
    "MONTO_RNR"          : "Monto_Estado",
    "MONTO_PROINNOVATE"  : "Monto_Estado",
    "MONTO_ESTADO"       : "Monto_Estado",
    "MONTO_FINANCIERO"   : "Aporte_Empresa",
    "APORTE_EMPRESA"     : "Aporte_Empresa",
    "MONTO_NO_FINANCIERO": "Aporte_No_Financiero",
    "FECHA_CORTE"        : "Fecha_Corte",
    "ANIO"               : "Anio_Proyecto",
    "CONCURSO"           : "Concurso",
    "FECHA_INICIO"       : "Fecha_Inicio",
    "FECHA_FIN"          : "Fecha_Fin",
    "UBIGEO"             : "Ubigeo",
    "PROVINCIA"          : "Provincia",
    "DISTRITO"           : "Distrito",
    "MONEDA"             : "Moneda_Original",
}

# La unidad de análisis es el contrato y no la empresa: una empresa puede
# ganar varios concursos y el nombre registrado de un mismo contrato cambia
# entre cortes (abreviaturas, orden de nombres, cambio de razón social).
LLAVE_PROYECTO = "Contrato"

COLS_REQUERIDAS = [
    "Contrato", "Empresa", "Titulo_Proyecto", "Fondo", "Region",
    "Monto_Estado", "Aporte_Empresa", "Fecha_Corte",
]
COLS_FINANCIERAS = ["Monto_Estado", "Aporte_Empresa", "Aporte_No_Financiero"]
COLS_TEXTO = [
    "Region", "Provincia", "Distrito", "Fondo", "Concurso", "Empresa", "Titulo_Proyecto",
]

# Proporción de nulos a partir de la cual una columna se descarta
UMBRAL_NULOS = 0.90

# Los fondos FINCYT y BID 4 registran parte de sus contratos en dólares. Para
# sumarlos con el resto se convierten a soles con el promedio anual del tipo de
# cambio bancario venta (S/ por US$) del año del concurso. Fuente: BCRP, serie
# PM05242PA. Los años sin promedio publicado usan el valor más cercano.
MONEDA_SOLES   = "SOLES"
MONEDA_DOLARES = "DOLARES"
TIPO_CAMBIO_ANUAL = {
    2007: 3.13, 2008: 2.93, 2009: 3.01, 2010: 2.83, 2011: 2.75,
    2012: 2.64, 2013: 2.70, 2014: 2.84, 2015: 3.19, 2016: 3.38,
    2017: 3.26, 2018: 3.29, 2019: 3.34, 2020: 3.50, 2021: 3.88,
    2022: 3.84, 2023: 3.75, 2024: 3.76, 2025: 3.57,
}

REGION_NO_DETERMINADA   = "NO DETERMINADO"
VALORES_REGION_SIN_DATO = {"N/D", "ND", "NO DEFINIDO", "-"}

# ==============================================================================
# Métricas financieras y territoriales
# ==============================================================================

CSV_RESUMEN_REGIONAL = DIR_SALIDAS / "resumen_regional.csv"

AMBITO_LIMA     = "LIMA METROPOLITANA Y CALLAO"
AMBITO_REGIONES = "REGIONES"

# Agrupación geográfica convencional de los departamentos del Perú. Lima y
# Callao forman su propio grupo porque concentran la mayoría de proyectos y
# ocultarían la distribución en el resto del país.
MACRORREGIONES = {
    "LIMA Y CALLAO": ["LIMA", "CALLAO"],
    "NORTE"        : ["TUMBES", "PIURA", "LAMBAYEQUE", "LA LIBERTAD", "CAJAMARCA", "ANCASH"],
    "CENTRO"       : ["HUANUCO", "PASCO", "JUNIN", "HUANCAVELICA", "ICA", "AYACUCHO"],
    "SUR"          : ["AREQUIPA", "MOQUEGUA", "TACNA", "PUNO", "CUSCO", "APURIMAC", "MADRE DE DIOS"],
    "ORIENTE"      : ["AMAZONAS", "SAN MARTIN", "LORETO", "UCAYALI"],
}

# ==============================================================================
# Fase 2: NLP y clustering
# ==============================================================================

CSV_EVALUACION_CLUSTERS = DIR_SALIDAS / "evaluacion_clusters.csv"
CSV_RESUMEN_CLUSTERS    = DIR_SALIDAS / "resumen_clusters.csv"

# Los títulos son textos cortos y el silhouette es bajo para cualquier k
# (0.07 a 0.14). k=10 es un máximo local: supera a 8 y a 12, separa temas que
# con 5 quedaban mezclados (ISO, HACCP, misiones tecnológicas, validación) y
# cada clúster sigue siendo interpretable. k=14 tiene un silhouette mayor pero
# fragmenta los temas en grupos pequeños. La evaluación queda en
# evaluacion_clusters.csv.
N_CLUSTERS          = 10
RANGO_K_EVALUACION  = [6, 8, 10, 12, 14]
MAX_CARACTERISTICAS = 1500
N_COMPONENTES       = 100
MIN_DOCUMENTOS      = 3     # descarta términos que aparecen en menos de 3 títulos
MAX_PROPORCION_DOCS = 0.5   # descarta términos presentes en más de la mitad
N_TERMINOS_CLUSTER  = 10
MUESTRA_SILHOUETTE  = 5000  # el silhouette es O(n²); una muestra basta para comparar k

# Términos frecuentes en los títulos que no describen la tecnología del
# proyecto: conectores, nombres de programas y palabras genéricas de gestión.
PALABRAS_VACIAS_EXTRA = {
    "para", "con", "del", "las", "los", "una", "uno", "sus", "ser",
    "esta", "este", "mediante", "traves", "hacia", "entre", "como",
    "mas", "sino", "ante", "bajo", "sobre", "desde", "hasta",
    "proyecto", "desarrollo", "implementacion", "sistema", "empresa",
    "nacional", "regional", "local", "peru", "peruano", "peruanos",
    "financiamiento", "cofinanciamiento", "innovacion", "innovate",
    "proinnovate", "fincyt", "fidecom", "fomitec", "concytec",
    "mejora", "mejoramiento", "fortalecimiento", "capacidades",
    "sac", "eirl", "srl", "empresas", "region", "departamento", "provincia", "distrito",
    "partir", "uso", "utilizando", "alto", "base", "basado", "nuevo", "nueva",
    "madre", "dios",
}

# Cada clúster recibe el sector cuyos términos pesan más en su centroide. Así
# el nombre depende del contenido del clúster y no de su número, que K-Means
# puede cambiar si se agregan cortes nuevos. Un término pertenece a un solo
# sector para que los puntajes no se repartan entre dos.
SECTORES_TECNOLOGICOS = {
    "CERTIFICACION Y CALIDAD": [
        "iso", "certificacion", "norma", "calidad", "gestion calidad", "haccp",
        "seguridad", "salud", "inocuidad", "ohsas", "acreditacion", "laboratorio",
        "trazabilidad", "buenas practicas",
    ],
    "TRANSFORMACION DIGITAL": [
        "digital", "digitales", "digitalizacion", "plataforma", "software", "web",
        "online", "virtual", "aplicativo", "app", "movil", "erp", "inteligente",
        "datos", "automatizacion", "comercio electronico", "transformacion digital",
    ],
    "AGROINDUSTRIA Y ALIMENTOS": [
        "cultivo", "cacao", "cafe", "alimentos", "agricola", "agroindustrial",
        "organica", "organico", "quinua", "frutas", "semillas", "leche",
        "acuicultura", "pesca", "harina", "ganado", "palta", "fertilizante",
    ],
    "MANUFACTURA Y PROCESOS": [
        "produccion", "proceso", "planta", "fabricacion", "industrial", "residuos",
        "tratamiento", "linea produccion", "equipo", "materiales", "procesamiento",
    ],
    "PROTOTIPADO Y VALIDACION": [
        "prototipo", "validacion", "empaquetamiento", "piloto", "escalamiento",
        "validacion tecnica", "tecnica comercial", "maquina",
    ],
    "INTERNACIONALIZACION": [
        "exportacion", "exportaciones", "internacionalizacion", "internacional",
        "mercado internacional", "consolidacion", "posicionamiento",
    ],
    "TRANSFERENCIA Y FORMACION": [
        "mision", "mision tecnologica", "feria", "bootcamp", "pasantia", "evento",
        "congreso", "seminario", "capacitacion", "incubadora", "emprendimiento",
        "emprendedores",
    ],
    "MARKETING Y GESTION COMERCIAL": [
        "marketing", "marketing digital", "ventas", "clientes", "comercial",
        "estrategia", "estrategias", "marca",
    ],
}

# Si ningún sector reúne al menos esta parte del puntaje de un clúster, el
# clúster mezcla temas y se etiqueta como multisectorial
SECTOR_MULTISECTORIAL    = "MULTISECTORIAL"
SECTOR_SIN_CLASIFICAR    = "SIN CLASIFICAR"
UMBRAL_DOMINANCIA_SECTOR = 0.35
SIN_CLUSTER              = -1
